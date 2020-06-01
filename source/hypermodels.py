# @author lucasmiranda42

from kerastuner import HyperModel
from tensorflow.keras import Input, Model, Sequential
from tensorflow.keras.constraints import UnitNorm
from tensorflow.keras.initializers import he_uniform, Orthogonal
from tensorflow.keras.layers import BatchNormalization, Bidirectional, Dense
from tensorflow.keras.layers import Dropout, Lambda, LSTM
from tensorflow.keras.layers import RepeatVector, TimeDistributed
from tensorflow.keras.losses import Huber
from tensorflow.keras.optimizers import Adam
from source.model_utils import *
import tensorflow as tf


class SEQ_2_SEQ_AE(HyperModel):
    def __init__(self, input_shape):
        super().__init__()
        self.input_shape = input_shape

    def build(self, hp):
        # Hyperparameters to tune
        CONV_filters = hp.Int(
            "units_conv", min_value=32, max_value=256, step=32, default=256
        )
        LSTM_units_1 = hp.Int(
            "units_lstm", min_value=128, max_value=512, step=32, default=256
        )
        LSTM_units_2 = int(LSTM_units_1 / 2)
        DENSE_1 = int(LSTM_units_2)
        DENSE_2 = hp.Int(
            "units_dense1", min_value=32, max_value=256, step=32, default=64
        )
        DROPOUT_RATE = hp.Float(
            "dropout_rate", min_value=0.0, max_value=0.5, default=0.25, step=0.05
        )
        ENCODING = hp.Int(
            "units_dense2", min_value=32, max_value=128, step=32, default=32
        )

        # Encoder Layers
        # Encoder Layers
        Model_E0 = tf.keras.layers.Conv1D(
            filters=CONV_filters,
            kernel_size=5,
            strides=1,
            padding="causal",
            activation="relu",
            kernel_initializer=he_uniform(),
        )
        Model_E1 = Bidirectional(
            LSTM(
                LSTM_units_1,
                activation="tanh",
                return_sequences=True,
                kernel_constraint=UnitNorm(axis=0),
            )
        )
        Model_E2 = Bidirectional(
            LSTM(
                LSTM_units_2,
                activation="tanh",
                return_sequences=False,
                kernel_constraint=UnitNorm(axis=0),
            )
        )
        Model_E3 = Dense(
            DENSE_1,
            activation="relu",
            kernel_constraint=UnitNorm(axis=0),
            kernel_initializer=he_uniform(),
        )
        Model_E4 = Dense(
            DENSE_2,
            activation="relu",
            kernel_constraint=UnitNorm(axis=0),
            kernel_initializer=he_uniform(),
        )
        Model_E5 = Dense(
            ENCODING,
            activation="relu",
            kernel_constraint=UnitNorm(axis=1),
            activity_regularizer=UncorrelatedFeaturesConstraint(3, weightage=1.0),
            kernel_initializer=Orthogonal(),
        )

        # Decoder layers
        Model_D0 = DenseTranspose(Model_E5, activation="relu", output_dim=ENCODING,)
        Model_D1 = DenseTranspose(Model_E4, activation="relu", output_dim=DENSE_2,)
        Model_D2 = DenseTranspose(Model_E3, activation="relu", output_dim=DENSE_1,)
        Model_D3 = RepeatVector(self.input_shape[1])
        Model_D4 = Bidirectional(
            LSTM(
                LSTM_units_1,
                activation="tanh",
                return_sequences=True,
                kernel_constraint=UnitNorm(axis=1),
            )
        )
        Model_D5 = Bidirectional(
            LSTM(
                LSTM_units_1,
                activation="sigmoid",
                return_sequences=True,
                kernel_constraint=UnitNorm(axis=1),
            )
        )

        # Define and instanciate encoder
        encoder = Sequential(name="SEQ_2_SEQ_Encoder")
        encoder.add(Input(shape=self.input_shape[1:]))
        encoder.add(Model_E0)
        encoder.add(BatchNormalization())
        encoder.add(Model_E1)
        encoder.add(BatchNormalization())
        encoder.add(Model_E2)
        encoder.add(BatchNormalization())
        encoder.add(Model_E3)
        encoder.add(BatchNormalization())
        encoder.add(Dropout(DROPOUT_RATE))
        encoder.add(Model_E4)
        encoder.add(BatchNormalization())
        encoder.add(Model_E5)

        # Define and instanciate decoder
        decoder = Sequential(name="SEQ_2_SEQ_Decoder")
        decoder.add(Model_D0)
        encoder.add(BatchNormalization())
        decoder.add(Model_D1)
        encoder.add(BatchNormalization())
        decoder.add(Model_D2)
        encoder.add(BatchNormalization())
        decoder.add(Model_D3)
        decoder.add(BatchNormalization())
        decoder.add(Model_D4)
        encoder.add(BatchNormalization())
        decoder.add(Model_D5)
        decoder.add(TimeDistributed(Dense(self.input_shape[2])))

        model = Sequential([encoder, decoder], name="SEQ_2_SEQ_AE")

        model.compile(
            loss=Huber(reduction="sum", delta=100.0),
            optimizer=Adam(
                lr=hp.Float(
                    "learning_rate",
                    min_value=1e-4,
                    max_value=1e-2,
                    sampling="LOG",
                    default=1e-3,
                ),
                clipvalue=0.5,
            ),
            metrics=["mae"],
        )

        return model


class SEQ_2_SEQ_VAE(HyperModel):
    def __init__(self, input_shape, loss="ELBO+MMD"):
        super().__init__()
        self.input_shape = input_shape
        self.loss = loss

        assert self.loss in [
            "MMD",
            "ELBO",
            "ELBO+MMD",
        ], "Loss function not recognised. Select one of ELBO, MMD and ELBO+MMD"

    def build(self, hp):

        # Hyperparameters to tune
        CONV_filters = hp.Int(
            "units_conv", min_value=32, max_value=256, step=32, default=256
        )
        LSTM_units_1 = hp.Int(
            "units_lstm", min_value=128, max_value=512, step=32, default=256
        )
        LSTM_units_2 = int(LSTM_units_1 / 2)
        DENSE_1 = int(LSTM_units_2)
        DENSE_2 = hp.Int(
            "units_dense1", min_value=32, max_value=256, step=32, default=64
        )
        DROPOUT_RATE = hp.Float(
            "dropout_rate", min_value=0.0, max_value=0.5, default=0.25, step=0.05
        )
        ENCODING = hp.Int(
            "units_dense2", min_value=32, max_value=128, step=32, default=32
        )

        # Encoder Layers
        Model_E0 = tf.keras.layers.Conv1D(
            filters=CONV_filters,
            kernel_size=5,
            strides=1,
            padding="causal",
            activation="relu",
            kernel_initializer=he_uniform(),
        )
        Model_E1 = Bidirectional(
            LSTM(
                LSTM_units_1,
                activation="tanh",
                return_sequences=True,
                kernel_constraint=UnitNorm(axis=0),
            )
        )
        Model_E2 = Bidirectional(
            LSTM(
                LSTM_units_2,
                activation="tanh",
                return_sequences=False,
                kernel_constraint=UnitNorm(axis=0),
            )
        )
        Model_E3 = Dense(
            DENSE_1,
            activation="relu",
            kernel_constraint=UnitNorm(axis=0),
            kernel_initializer=he_uniform(),
        )
        Model_E4 = Dense(
            DENSE_2,
            activation="relu",
            kernel_constraint=UnitNorm(axis=0),
            kernel_initializer=he_uniform(),
        )
        Model_E5 = Dense(
            ENCODING,
            activation="relu",
            kernel_constraint=UnitNorm(axis=1),
            activity_regularizer=UncorrelatedFeaturesConstraint(3, weightage=1.0),
            kernel_initializer=Orthogonal(),
        )

        # Decoder layers
        Model_D0 = DenseTranspose(Model_E5, activation="relu", output_dim=ENCODING,)
        Model_D1 = DenseTranspose(Model_E4, activation="relu", output_dim=DENSE_2,)
        Model_D2 = DenseTranspose(Model_E3, activation="relu", output_dim=DENSE_1,)
        Model_D3 = RepeatVector(self.input_shape[1])
        Model_D4 = Bidirectional(
            LSTM(
                LSTM_units_1,
                activation="tanh",
                return_sequences=True,
                kernel_constraint=UnitNorm(axis=1),
            )
        )
        Model_D5 = Bidirectional(
            LSTM(
                LSTM_units_1,
                activation="sigmoid",
                return_sequences=True,
                kernel_constraint=UnitNorm(axis=1),
            )
        )

        # Define and instanciate encoder
        x = Input(shape=self.input_shape[1:])
        encoder = Model_E0(x)
        encoder = BatchNormalization()(encoder)
        encoder = Model_E1(encoder)
        encoder = BatchNormalization()(encoder)
        encoder = Model_E2(encoder)
        encoder = BatchNormalization()(encoder)
        encoder = Model_E3(encoder)
        encoder = BatchNormalization()(encoder)
        encoder = Dropout(DROPOUT_RATE)(encoder)
        encoder = Model_E4(encoder)
        encoder = BatchNormalization()(encoder)
        encoder = Model_E5(encoder)

        z_mean = Dense(ENCODING)(encoder)
        z_log_sigma = Dense(ENCODING)(encoder)

        if "ELBO" in self.loss:
            z_mean, z_log_sigma = KLDivergenceLayer()([z_mean, z_log_sigma])

        z = Lambda(sampling)([z_mean, z_log_sigma])

        if "MMD" in self.loss:
            z = MMDiscrepancyLayer()(z)

        # Define and instanciate generator
        generator = Model_D0(z)
        generator = BatchNormalization()(generator)
        generator = Model_D1(generator)
        generator = BatchNormalization()(generator)
        generator = Model_D2(generator)
        generator = BatchNormalization()(generator)
        generator = Model_D3(generator)
        generator = BatchNormalization()(generator)
        generator = Model_D4(generator)
        generator = BatchNormalization()(generator)
        generator = Model_D5(generator)
        x_decoded_mean = TimeDistributed(Dense(self.input_shape[2]))(generator)

        # end-to-end autoencoder
        vae = Model(x, x_decoded_mean, name="SEQ_2_SEQ_VAE")

        def huber_loss(x_, x_decoded_mean_):
            huber = Huber(reduction="sum", delta=100.0)
            return self.input_shape[1:] * huber(x_, x_decoded_mean_)

        vae.compile(
            loss=huber_loss,
            optimizer=Adam(
                lr=hp.Float(
                    "learning_rate",
                    min_value=1e-4,
                    max_value=1e-2,
                    sampling="LOG",
                    default=1e-3,
                ),
            ),
            metrics=["mae"],
            experimental_run_tf_function=False,
        )

        return vae


class SEQ_2_SEQ_VAEP(HyperModel):
    def __init__(self, input_shape, loss="ELBO+MMD"):
        super().__init__()
        self.input_shape = input_shape
        self.loss = loss

    def build(self, hp):
        # Hyperparameters to tune
        CONV_filters = hp.Int(
            "units_conv", min_value=32, max_value=256, step=32, default=256
        )
        LSTM_units_1 = hp.Int(
            "units_lstm", min_value=128, max_value=512, step=32, default=256
        )
        LSTM_units_2 = int(LSTM_units_1 / 2)
        DENSE_1 = int(LSTM_units_2)
        DENSE_2 = hp.Int(
            "units_dense1", min_value=32, max_value=256, step=32, default=64
        )
        DROPOUT_RATE = hp.Float(
            "dropout_rate", min_value=0.0, max_value=0.5, default=0.25, step=0.05
        )
        ENCODING = hp.Int(
            "units_dense2", min_value=32, max_value=128, step=32, default=32
        )

        # Encoder Layers
        Model_E0 = tf.keras.layers.Conv1D(
            filters=CONV_filters,
            kernel_size=5,
            strides=1,
            padding="causal",
            activation="relu",
            kernel_initializer=he_uniform(),
        )
        Model_E1 = Bidirectional(
            LSTM(
                LSTM_units_1,
                activation="tanh",
                return_sequences=True,
                kernel_constraint=UnitNorm(axis=0),
            )
        )
        Model_E2 = Bidirectional(
            LSTM(
                LSTM_units_2,
                activation="tanh",
                return_sequences=False,
                kernel_constraint=UnitNorm(axis=0),
            )
        )
        Model_E3 = Dense(
            DENSE_1,
            activation="relu",
            kernel_constraint=UnitNorm(axis=0),
            kernel_initializer=he_uniform(),
        )
        Model_E4 = Dense(
            DENSE_2,
            activation="relu",
            kernel_constraint=UnitNorm(axis=0),
            kernel_initializer=he_uniform(),
        )
        Model_E5 = Dense(
            ENCODING,
            activation="relu",
            kernel_constraint=UnitNorm(axis=1),
            activity_regularizer=UncorrelatedFeaturesConstraint(3, weightage=1.0),
            kernel_initializer=Orthogonal(),
        )

        # Decoder layers
        Model_B1 = BatchNormalization()
        Model_B2 = BatchNormalization()
        Model_B3 = BatchNormalization()
        Model_B4 = BatchNormalization()
        Model_B5 = BatchNormalization()
        Model_D0 = DenseTranspose(Model_E5, activation="relu", output_dim=ENCODING,)
        Model_D1 = DenseTranspose(Model_E4, activation="relu", output_dim=DENSE_2,)
        Model_D2 = DenseTranspose(Model_E3, activation="relu", output_dim=DENSE_1,)
        Model_D3 = RepeatVector(self.input_shape[1])
        Model_D4 = Bidirectional(
            LSTM(
                LSTM_units_1,
                activation="tanh",
                return_sequences=True,
                kernel_constraint=UnitNorm(axis=1),
            )
        )
        Model_D5 = Bidirectional(
            LSTM(
                LSTM_units_1,
                activation="sigmoid",
                return_sequences=True,
                kernel_constraint=UnitNorm(axis=1),
            )
        )

        # Define and instantiate encoder
        x = Input(shape=self.input_shape[1:])
        encoder = Model_E0(x)
        encoder = BatchNormalization()(encoder)
        encoder = Model_E1(encoder)
        encoder = BatchNormalization()(encoder)
        encoder = Model_E2(encoder)
        encoder = BatchNormalization()(encoder)
        encoder = Model_E3(encoder)
        encoder = BatchNormalization()(encoder)
        encoder = Dropout(DROPOUT_RATE)(encoder)
        encoder = Model_E4(encoder)
        encoder = BatchNormalization()(encoder)
        encoder = Model_E5(encoder)

        z_mean = Dense(ENCODING)(encoder)
        z_log_sigma = Dense(ENCODING)(encoder)

        if "ELBO" in self.loss:
            z_mean, z_log_sigma = KLDivergenceLayer()([z_mean, z_log_sigma])

        z = Lambda(sampling)([z_mean, z_log_sigma])

        if "MMD" in self.loss:
            z = MMDiscrepancyLayer()(z)

        # Define and instantiate generator
        generator = Model_D0(z)
        generator = Model_B1(generator)
        generator = Model_D1(generator)
        generator = Model_B2(generator)
        generator = Model_D2(generator)
        generator = Model_B3(generator)
        generator = Model_D3(generator)
        generator = Model_D4(generator)
        generator = Model_B4(generator)
        generator = Model_D5(generator)
        generator = Model_B5(generator)
        x_decoded_mean = TimeDistributed(Dense(self.input_shape[2]))(generator)

        # Define and instantiate predictor
        predictor = Dense(ENCODING, activation="relu", kernel_initializer=he_uniform())(
            z
        )
        predictor = BatchNormalization()(predictor)
        predictor = Dense(DENSE_2, activation="relu", kernel_initializer=he_uniform())(
            predictor
        )
        predictor = BatchNormalization()(predictor)
        predictor = Dense(DENSE_1, activation="relu", kernel_initializer=he_uniform())(
            predictor
        )
        predictor = BatchNormalization()(predictor)
        predictor = RepeatVector(self.input_shape[1])(predictor)
        predictor = Bidirectional(
            LSTM(
                LSTM_units_1,
                activation="tanh",
                return_sequences=True,
                kernel_constraint=UnitNorm(axis=1),
            )
        )(predictor)
        predictor = BatchNormalization()(predictor)
        predictor = Bidirectional(
            LSTM(
                LSTM_units_1,
                activation="sigmoid",
                return_sequences=True,
                kernel_constraint=UnitNorm(axis=1),
            )
        )(predictor)
        predictor = BatchNormalization()(predictor)
        x_predicted_mean = TimeDistributed(Dense(self.input_shape[2]))(predictor)

        # end-to-end autoencoder
        vaep = Model(
            inputs=x, outputs=[x_decoded_mean, x_predicted_mean], name="SEQ_2_SEQ_VAE"
        )

        def huber_loss(x_, x_decoded_mean_):
            huber = Huber(reduction="sum", delta=100.0)
            return self.input_shape[1:] * huber(x_, x_decoded_mean_)

        vaep.compile(
            loss=huber_loss,
            optimizer=Adam(
                lr=hp.Float(
                    "learning_rate",
                    min_value=1e-4,
                    max_value=1e-2,
                    sampling="LOG",
                    default=1e-3,
                ),
            ),
            metrics=["mae"],
            experimental_run_tf_function=False,
        )

        return vaep


class SEQ_2_SEQ_MMVAE(HyperModel):
    def __init__(self, input_shape):
        super().__init__()
        self.input_shape = input_shape

    def build(self, hp):
        pass
