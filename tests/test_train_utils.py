# @author lucasmiranda42
# encoding: utf-8
# module deepof

"""

Testing module for deepof.train_utils

"""

from hypothesis import given
from hypothesis import settings, reproduce_failure
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays
import deepof.data
import deepof.model_utils
import deepof.train_utils
import os
import tensorflow as tf


def test_load_hparams():
    assert type(deepof.train_utils.load_hparams(None)) == dict
    assert (
        type(
            deepof.train_utils.load_hparams(
                os.path.join(
                    "tests",
                    "test_examples",
                    "test_single_topview",
                    "Others",
                    "test_hparams.pkl",
                )
            )
        )
        == dict
    )


def test_load_treatments():
    assert deepof.train_utils.load_treatments(".") is None
    assert (
        type(
            deepof.train_utils.load_treatments(
                os.path.join("tests", "test_examples", "test_single_topview", "Others")
            )
        )
        == dict
    )


@given(
    X_train=arrays(
        shape=st.tuples(st.integers(min_value=1, max_value=1000)),
        dtype=float,
        elements=st.floats(
            min_value=0.0,
            max_value=1,
        ),
    ),
    batch_size=st.integers(min_value=128, max_value=512),
    loss=st.one_of(st.just("test_A"), st.just("test_B")),
    predictor=st.floats(min_value=0.0, max_value=1.0),
    pheno_class=st.floats(min_value=0.0, max_value=1.0),
    variational=st.booleans(),
)
def test_get_callbacks(
    X_train,
    batch_size,
    variational,
    predictor,
    pheno_class,
    loss,
):
    runID, tbc, cycle1c, cpc = deepof.train_utils.get_callbacks(
        X_train, batch_size, True, variational, pheno_class, predictor, loss, None
    )
    assert type(runID) == str
    assert type(tbc) == tf.keras.callbacks.TensorBoard
    assert type(cpc) == tf.keras.callbacks.ModelCheckpoint
    assert type(cycle1c) == deepof.model_utils.one_cycle_scheduler


@settings(max_examples=10, deadline=None)
@given(
    X_train=arrays(
        dtype=float,
        shape=st.tuples(
            st.integers(min_value=10, max_value=100),
            st.integers(min_value=2, max_value=15),
            st.integers(min_value=2, max_value=10),
        ),
        elements=st.floats(
            min_value=0.0,
            max_value=1,
        ),
    ),
    batch_size=st.integers(min_value=128, max_value=512),
    encoding_size=st.integers(min_value=1, max_value=16),
    k=st.integers(min_value=1, max_value=10),
    loss=st.one_of(st.just("ELBO"), st.just("MMD")),
    pheno_class=st.floats(min_value=0.0, max_value=1.0),
    predictor=st.floats(min_value=0.0, max_value=1.0),
    variational=st.booleans(),
)
def test_autoencoder_fitting(
    X_train,
    batch_size,
    encoding_size,
    k,
    loss,
    pheno_class,
    predictor,
    variational,
):
    preprocessed_data = (X_train, [], X_train, [])

    prun = deepof.data.project(
        path=os.path.join(".", "tests", "test_examples", "test_single_topview"),
        arena="circular",
        arena_dims=tuple([380]),
        video_format=".mp4",
    ).run()

    models = prun.deep_unsupervised_embedding(
        preprocessed_data,
        batch_size=batch_size,
        encoding_size=encoding_size,
        epochs=1,
        log_history=True,
        log_hparams=True,
        n_components=k,
        loss=loss,
        phenotype_class=0,
        predictor=predictor,
        variational=variational,
    )
    print(models)


@settings(max_examples=1, deadline=None)
@given(
    X_train=arrays(
        dtype=float,
        shape=st.tuples(
            st.integers(min_value=10, max_value=100),
            st.integers(min_value=2, max_value=15),
            st.integers(min_value=2, max_value=10),
        ),
        elements=st.floats(
            min_value=0.0,
            max_value=1,
        ),
    ),
    batch_size=st.integers(min_value=128, max_value=512),
    encoding_size=st.integers(min_value=1, max_value=16),
    hpt_type=st.one_of(st.just("bayopt"), st.just("hypermodel")),
    hypermodel=st.just("S2SGMVAE"),
    k=st.integers(min_value=1, max_value=10),
    loss=st.one_of(st.just("ELBO"), st.just("MMD")),
    overlap_loss=st.floats(min_value=0.0, max_value=1.0),
    pheno_class=st.floats(min_value=0.0, max_value=1.0),
    predictor=st.floats(min_value=0.0, max_value=1.0),
)
def test_tune_search(
    X_train,
    batch_size,
    encoding_size,
    hpt_type,
    hypermodel,
    k,
    loss,
    overlap_loss,
    pheno_class,
    predictor,
):
    callbacks = list(
        deepof.train_utils.get_callbacks(
            X_train,
            batch_size,
            False,
            hypermodel == "S2SGMVAE",
            0,
            predictor,
            loss,
            None,
        )
    )[1:]

    y_train = tf.random.uniform(shape=(X_train.shape[1],), maxval=1.0)

    deepof.train_utils.tune_search(
        data=[X_train, y_train, X_train, y_train],
        encoding_size=encoding_size,
        hpt_type=hpt_type,
        hypertun_trials=1,
        hypermodel=hypermodel,
        k=k,
        kl_warmup_epochs=0,
        loss=loss,
        mmd_warmup_epochs=0,
        overlap_loss=overlap_loss,
        phenotype_class=pheno_class,
        predictor=predictor,
        project_name="test_run",
        callbacks=callbacks,
        n_epochs=1,
    )
