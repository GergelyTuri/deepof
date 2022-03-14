# @author lucasmiranda42
# encoding: utf-8
# module deepof

"""

deep autoencoder model for unsupervised pose detection.
Based on VQ-VAE: a variational autoencoder with a vector quantization latent-space (https://arxiv.org/abs/1711.00937).

"""

import tensorflow as tf
import tensorflow_probability as tfp
from tensorflow.keras import Input, Model
from tensorflow.keras.initializers import he_uniform
from tensorflow.keras.layers import Dense, GRU, RepeatVector, TimeDistributed
from tensorflow.keras.layers import LayerNormalization, Bidirectional

import deepof.model_utils

tfb = tfp.bijectors
tfd = tfp.distributions
tfpl = tfp.layers

# noinspection PyCallingNonCallable
def get_deepof_encoder(
    input_shape,
    conv_filters=64,
    dense_activation="relu",
    gru_units_1=32,
    gru_unroll=False,
    bidirectional_merge="concat",
):
    """

    Returns a deep neural network capable of encoding the motion tracking instances into a vector ready to be fed to
    one of the provided structured latent spaces.

    Args:
        input_shape (tuple): shape of the input data
        conv_filters (int): number of filters in the first convolutional layer
        dense_activation (str): activation function for the dense layers. Defaults to "relu".
        gru_units_1 (int): number of units in the first GRU layer. Defaults to 128.
        gru_unroll (bool): whether to unroll the GRU layers. Defaults to False.
        bidirectional_merge (str): how to merge the forward and backward GRU layers. Defaults to "concat".

    Returns:
        keras.Model: a keras model that can be trained to encode motion tracking instances into a vector.

    """

    # Define and instantiate encoder
    x = Input(shape=input_shape)
    encoder = tf.keras.layers.Conv1D(
        filters=conv_filters,
        kernel_size=5,
        strides=1,  # Increased strides yield shorter sequences
        padding="same",
        activation=dense_activation,
        kernel_initializer=he_uniform(),
        use_bias=False,
    )(x)
    encoder = tf.keras.layers.Masking(mask_value=0.0)(encoder)
    encoder = Bidirectional(
        GRU(
            gru_units_1,
            activation="tanh",
            recurrent_activation="sigmoid",
            return_sequences=True,
            unroll=gru_unroll,
            use_bias=True,
        ),
        merge_mode=bidirectional_merge,
    )(encoder)
    encoder = LayerNormalization()(encoder)
    encoder = Bidirectional(
        GRU(
            gru_units_1 // 2,
            activation="tanh",
            recurrent_activation="sigmoid",
            return_sequences=False,
            unroll=gru_unroll,
            use_bias=True,
        ),
        merge_mode=bidirectional_merge,
    )(encoder)
    encoder_output = LayerNormalization()(encoder)

    return Model(x, encoder_output, name="deepof_encoder")


# noinspection PyCallingNonCallable
def get_deepof_decoder(
    input_shape,
    latent_dim,
    conv_filters=64,
    dense_activation="relu",
    gru_units_1=32,
    gru_unroll=False,
    bidirectional_merge="concat",
):

    """

    Returns a deep neural network capable of decoding the structured latent space generated by one of the compatible
    classes into a sequence of motion tracking instances, either reconstructing the original
    input, or generating new data from given clusters.

    Args:
        input_shape (tuple): shape of the input data
        latent_dim (int): dimensionality of the latent space
        conv_filters (int): number of filters in the first convolutional layer
        dense_activation (str): activation function for the dense layers. Defaults to "relu".
        gru_units_1 (int): number of units in the first GRU layer. Defaults to 128.
        gru_unroll (bool): whether to unroll the GRU layers. Defaults to False.
        bidirectional_merge (str): how to merge the forward and backward GRU layers. Defaults to "concat".

    Returns:
        keras.Model: a keras model that can be trained to decode the latent space into a series of motion tracking
        sequences.

    """

    # Define and instantiate generator
    g = Input(shape=latent_dim)  # Decoder input, shaped as the latent space
    x = Input(shape=input_shape)  # Encoder input, used to generate an output mask
    validity_mask = tf.math.logical_not(tf.reduce_all(x == 0.0, axis=2))

    generator = RepeatVector(input_shape[0])(g)
    generator = Bidirectional(
        GRU(
            gru_units_1 // 2,
            activation="tanh",
            recurrent_activation="sigmoid",
            return_sequences=True,
            unroll=gru_unroll,
            use_bias=True,
        ),
        merge_mode=bidirectional_merge,
    )(generator, mask=validity_mask)
    generator = LayerNormalization()(generator)
    generator = Bidirectional(
        GRU(
            gru_units_1,
            activation="tanh",
            recurrent_activation="sigmoid",
            return_sequences=True,
            unroll=gru_unroll,
            use_bias=True,
        ),
        merge_mode=bidirectional_merge,
    )(generator)
    generator = LayerNormalization()(generator)
    generator = tf.keras.layers.Conv1D(
        filters=conv_filters,
        kernel_size=5,
        strides=1,
        padding="same",
        activation=dense_activation,
        kernel_initializer=he_uniform(),
        use_bias=False,
    )(generator)
    generator = LayerNormalization()(generator)
    x_decoded_mean = TimeDistributed(
        Dense(tfpl.IndependentNormal.params_size(input_shape[1:]) // 2)
    )(generator)

    # Add a skip connection, adding information directly from the latent space to propagate through the decoder
    # early in training.
    x_decoded_mean = tf.keras.layers.Add()([x_decoded_mean, Dense(input_shape[-1])(g)])

    x_decoded = tfpl.DistributionLambda(
        make_distribution_fn=lambda decoded: tfd.Masked(
            tfd.Independent(
                tfd.Normal(
                    loc=decoded[0],
                    scale=tf.ones_like(decoded[0]),
                    validate_args=False,
                    allow_nan_stats=False,
                ),
                reinterpreted_batch_ndims=1,
            ),
            validity_mask=decoded[1],
        ),
        convert_to_tensor_fn="mean",
    )([x_decoded_mean, validity_mask])

    # Zero out values that are not in the initial mask
    x_decoded = tfpl.DistributionLambda(
        make_distribution_fn=lambda decoded: tfd.Masked(
            tfd.TransformedDistribution(
                decoded[0],
                tfb.Scale(tf.cast(tf.expand_dims(decoded[1], axis=2), tf.float32)),
                name="vae_reconstruction",
            ),
            validity_mask=decoded[1],
        ),
        convert_to_tensor_fn="mean",
    )([x_decoded, validity_mask])

    return Model([g, x], x_decoded, name="deepof_decoder")


# noinspection PyCallingNonCallable
def get_vqvae(
    input_shape: tuple,
    latent_dim: int,
    n_components: int,
    beta: float = 1.0,
    reg_gram: float = 0.0,
    conv_filters=64,
    dense_activation="relu",
    gru_units_1=32,
    gru_unroll=False,
    bidirectional_merge="concat",
):
    """

    Builds a Vector-Quantization variational autoencoder (VQ-VAE) model, adapted to the DeepOF setting.

    Args:
        input_shape (tuple): shape of the input to the encoder.
        latent_dim (int): dimension of the latent space.
        n_components (int): number of embeddings in the embedding layer.
        beta (float): beta parameter of the VQ loss.
        reg_gram (float): regularization parameter for the Gram matrix.
        conv_filters (int): number of filters in the first convolutional layers ib both encoder and decoder.
        dense_activation (str): activation function for the dense layers in both encoder and decoder. Defaults to "relu".
        gru_units_1 (int): number of units in the first GRU layer in both encoder and decoder. Defaults to 128.
        gru_unroll (bool): whether to unroll the GRU layers. Defaults to False.
        bidirectional_merge (str): how to merge the forward and backward GRU layers. Defaults to "concat".

    Returns:
        encoder (tf.keras.Model): connected encoder of the VQ-VAE model.
        Outputs a vector of shape (latent_dim,).
        decoder (tf.keras.Model): connected decoder of the VQ-VAE model.
        quantizer (tf.keras.Model): connected embedder layer of the VQ-VAE model.
        Outputs cluster indices of shape (batch_size,).
        vqvae (tf.keras.Model): complete VQ VAE model.

    """
    vq_layer = deepof.model_utils.VectorQuantizer(
        n_components,
        latent_dim,
        beta=beta,
        reg_gram=reg_gram,
        name="vector_quantizer",
    )
    encoder = get_deepof_encoder(
        input_shape=input_shape,
        conv_filters=conv_filters,
        dense_activation=dense_activation,
        gru_units_1=gru_units_1,
        gru_unroll=gru_unroll,
        bidirectional_merge=bidirectional_merge,
    )
    decoder = get_deepof_decoder(
        input_shape=input_shape,
        latent_dim=latent_dim,
        conv_filters=conv_filters,
        dense_activation=dense_activation,
        gru_units_1=gru_units_1,
        gru_unroll=gru_unroll,
        bidirectional_merge=bidirectional_merge,
    )

    # Connect encoder and quantizer
    inputs = tf.keras.layers.Input(input_shape, name="encoder_input")
    encoder_outputs = encoder(inputs)
    quantized_latents, soft_counts = vq_layer(encoder_outputs)

    encoder = tf.keras.Model(inputs, encoder_outputs, name="encoder")
    quantizer = tf.keras.Model(inputs, quantized_latents, name="quantizer")
    soft_quantizer = tf.keras.Model(inputs, soft_counts, name="soft_quantizer")
    vqvae = tf.keras.Model(
        quantizer.inputs, decoder([quantizer.outputs, inputs]), name="VQ-VAE"
    )

    return (
        encoder,
        decoder,
        quantizer,
        soft_quantizer,
        vqvae,
    )


class VectorQuantizer(tf.keras.models.Model):
    """

    Vector quantizer layer, which quantizes the input vectors into a fixed number of clusters using L2 norm. Based on
    https://arxiv.org/pdf/1509.03700.pdf. Implementation based on https://keras.io/examples/generative/vq_vae/.

    """

    def __init__(
        self, n_components, embedding_dim, beta, reg_gram: float = 0.0, **kwargs
    ):
        """

        Initializes the VQ layer.

        Args:
            n_components (int): number of embeddings to use
            embedding_dim (int): dimensionality of the embeddings
            beta (float): beta value for the loss function
            reg_gram (float): regularization parameter for the Gram matrix
            **kwargs: additional arguments for the parent class

        """

        super(VectorQuantizer, self).__init__(**kwargs)
        self.embedding_dim = embedding_dim
        self.n_components = n_components
        self.beta = beta
        self.reg_gram = reg_gram

        # Initialize embedding layer
        self.embedding = tf.keras.layers.Dense(
            self.embedding_dim,
            kernel_initializer="he_uniform",
        )

        # Initialize the VQ codebook
        w_init = far_uniform_initializer(
            shape=[self.embedding_dim, self.n_components], samples=10000
        )
        self.codebook = tf.Variable(
            initial_value=w_init,
            trainable=True,
            name="vqvae_codebook",
        )

    def call(self, x):  # pragma: no cover
        """

        Computes the VQ layer.

        Args:
            x (tf.Tensor): input tensor

        Returns:
                x (tf.Tensor): output tensor

        """

        # Compute input shape and flatten, keeping the embedding dimension intact
        x = self.embedding(x)
        input_shape = tf.shape(x)

        # Add a disentangling penalty to the embeddings
        if self.reg_gram:
            gram_loss = compute_gram_loss(
                x, weight=self.reg_gram, batch_size=input_shape[0]
            )
            self.add_loss(gram_loss)
            self.add_metric(gram_loss, name="gram_loss")

        flattened = tf.reshape(x, [-1, self.embedding_dim])

        # Quantize input using the codebook
        encoding_indices = tf.cast(
            self.get_code_indices(flattened, return_soft_counts=False), tf.int32
        )
        soft_counts = self.get_code_indices(flattened, return_soft_counts=True)

        encodings = tf.one_hot(encoding_indices, self.n_components)

        quantized = tf.matmul(encodings, self.codebook, transpose_b=True)
        quantized = tf.reshape(quantized, input_shape)

        # Compute vector quantization loss, and add it to the layer
        commitment_loss = self.beta * tf.reduce_sum(
            (tf.stop_gradient(quantized) - x) ** 2
        )
        codebook_loss = tf.reduce_sum((quantized - tf.stop_gradient(x)) ** 2)
        self.add_loss(commitment_loss + codebook_loss)

        # Straight-through estimator (copy gradients through the undiferentiable layer)
        quantized = x + tf.stop_gradient(quantized - x)

        return quantized, soft_counts

    def get_code_indices(
        self, flattened_inputs, return_soft_counts=False
    ):  # pragma: no cover
        """

        Getter for the code indices at any given time.

        Args:
            input_shape (tf.Tensor): input shape
            flattened_inputs (tf.Tensor): flattened input tensor (encoder output)
            return_soft_counts (bool): whether to return soft counts based on the distance to the codes, instead of
            the code indices

        Returns:
            encoding_indices (tf.Tensor): code indices tensor with cluster assignments.

        """
        # Compute L2-norm distance between inputs and codes at a given time
        similarity = tf.matmul(flattened_inputs, self.codebook)
        distances = (
            tf.reduce_sum(flattened_inputs ** 2, axis=1, keepdims=True)
            + tf.reduce_sum(self.codebook ** 2, axis=0)
            - 2 * similarity
        )

        if return_soft_counts:
            # Compute soft counts based on the distance to the codes
            similarity = tf.reshape(1 / distances, [-1, self.n_components])
            soft_counts = tf.nn.softmax(similarity, axis=1)
            return soft_counts

        # Return index of the closest code
        encoding_indices = tf.argmin(distances, axis=1)
        return encoding_indices


class VQVAE(tf.keras.models.Model):
    """

    VQ-VAE model adapted to the DeepOF setting.

    """

    def __init__(
        self,
        input_shape: tuple,
        latent_dim: int = 4,
        n_components: int = 15,
        beta: float = 1.0,
        reg_gram: float = 0.0,
        architecture_hparams: dict = None,
        **kwargs,
    ):
        """

        Initializes a VQ-VAE model.

        Args:
            input_shape (tuple): Shape of the input to the full model.
            latent_dim (int): Dimensionality of the latent space.
            n_components (int): Number of embeddings (clusters) in the embedding layer.
            beta (float): Beta parameter of the VQ loss, as described in the original VQVAE paper.
            reg_gram (float): Regularization parameter for the Gram matrix.
            architecture_hparams (dict): Dictionary of architecture hyperparameters. Defaults to None.
            **kwargs: Additional keyword arguments.

        """

        super(VQVAE, self).__init__(**kwargs)
        self.seq_shape = input_shape[1:]
        self.latent_dim = latent_dim
        self.n_components = n_components
        self.beta = beta
        self.reg_gram = reg_gram
        self.architecture_hparams = architecture_hparams

        # Define VQ_VAE model
        (
            self.encoder,
            self.decoder,
            self.quantizer,
            self.soft_quantizer,
            self.vqvae,
        ) = get_vqvae(
            self.seq_shape,
            self.latent_dim,
            self.n_components,
            self.beta,
            self.reg_gram,
            conv_filters=self.hparams["conv_filters"],
            dense_activation=self.hparams["dense_activation"],
            gru_units_1=self.hparams["gru_units_1"],
            gru_unroll=self.hparams["gru_unroll"],
            bidirectional_merge=self.hparams["bidirectional_merge"],
        )

        # Define metrics to track
        self.total_loss_tracker = tf.keras.metrics.Mean(name="total_loss")
        self.reconstruction_loss_tracker = tf.keras.metrics.Mean(
            name="reconstruction_loss"
        )
        self.vq_loss_tracker = tf.keras.metrics.Mean(name="vq_loss")
        self.cluster_population = tf.keras.metrics.Mean(
            name="number_of_populated_clusters"
        )
        self.val_total_loss_tracker = tf.keras.metrics.Mean(name="total_loss")
        self.val_reconstruction_loss_tracker = tf.keras.metrics.Mean(
            name="reconstruction_loss"
        )
        self.val_vq_loss_tracker = tf.keras.metrics.Mean(name="vq_loss")
        self.val_cluster_population = tf.keras.metrics.Mean(
            name="number_of_populated_clusters"
        )

    @tf.function
    def call(self, inputs, **kwargs):
        return self.vqvae(inputs, **kwargs)

    @property
    def metrics(self):  # pragma: no cover
        return [
            self.total_loss_tracker,
            self.reconstruction_loss_tracker,
            self.vq_loss_tracker,
            self.cluster_population,
            self.val_total_loss_tracker,
            self.val_reconstruction_loss_tracker,
            self.val_vq_loss_tracker,
            self.val_cluster_population,
        ]

    @property
    def hparams(self):
        hparams = {
            "conv_filters": 64,
            "dense_activation": "relu",
            "gru_units_1": 32,
            "gru_unroll": False,
            "bidirectional_merge": "concat",
        }
        if self.architecture_hparams is not None:
            hparams.update(self.architecture_hparams)

        return hparams

    @tf.function
    def train_step(self, data):  # pragma: no cover
        """

        Performs a training step.

        """

        # Unpack data, repacking labels into a generator
        x, y = data
        if not isinstance(y, tuple):
            y = [y]
        y = (labels for labels in y)

        with tf.GradientTape() as tape:
            # Get outputs from the full model
            reconstructions = self.vqvae(x, training=True)

            # Compute losses
            reconstruction_loss = -tf.reduce_sum(reconstructions.log_prob(next(y)))
            total_loss = reconstruction_loss + sum(self.vqvae.losses)

        # Backpropagation
        grads = tape.gradient(total_loss, self.vqvae.trainable_variables)
        self.optimizer.apply_gradients(zip(grads, self.vqvae.trainable_variables))

        # Compute populated clusters
        unique_indices = tf.unique(
            tf.reshape(tf.argmax(self.soft_quantizer(x), axis=1), [-1])
        ).y
        populated_clusters = tf.shape(unique_indices)[0]

        # Track losses
        self.total_loss_tracker.update_state(total_loss)
        self.reconstruction_loss_tracker.update_state(reconstruction_loss)
        self.vq_loss_tracker.update_state(sum(self.vqvae.losses))
        self.cluster_population.update_state(populated_clusters)

        # Log results (coupled with TensorBoard)
        log_dict = {
            "total_loss": self.total_loss_tracker.result(),
            "reconstruction_loss": self.reconstruction_loss_tracker.result(),
            "vq_loss": self.vq_loss_tracker.result(),
            "number_of_populated_clusters": self.cluster_population.result(),
        }

        return {**log_dict, **{met.name: met.result() for met in self.vqvae.metrics}}

    @tf.function
    def test_step(self, data):  # pragma: no cover
        """

        Performs a test step.

        """

        # Unpack data, repacking labels into a generator
        x, y = data
        if not isinstance(y, tuple):
            y = [y]
        y = (labels for labels in y)

        # Get outputs from the full model
        reconstructions = self.vqvae(x, training=False)

        # Compute losses
        reconstruction_loss = -tf.reduce_sum(reconstructions.log_prob(next(y)))
        total_loss = reconstruction_loss + sum(self.vqvae.losses)

        # Compute populated clusters
        unique_indices = tf.unique(
            tf.reshape(tf.argmax(self.soft_quantizer(x), axis=1), [-1])
        ).y
        populated_clusters = tf.shape(unique_indices)[0]

        # Track losses
        self.val_total_loss_tracker.update_state(total_loss)
        self.val_reconstruction_loss_tracker.update_state(reconstruction_loss)
        self.val_vq_loss_tracker.update_state(sum(self.vqvae.losses))
        self.val_cluster_population.update_state(populated_clusters)

        # Log results (coupled with TensorBoard)
        log_dict = {
            "total_loss": self.val_total_loss_tracker.result(),
            "reconstruction_loss": self.val_reconstruction_loss_tracker.result(),
            "vq_loss": self.val_vq_loss_tracker.result(),
            "number_of_populated_clusters": self.val_cluster_population.result(),
        }

        return {**log_dict, **{met.name: met.result() for met in self.vqvae.metrics}}
