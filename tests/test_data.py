# @author lucasmiranda42
# encoding: utf-8
# module deepof

"""

Testing module for deepof.preprocess

"""

import os
from collections import defaultdict

import numpy as np
import pytest
from hypothesis import given
from hypothesis import settings
from hypothesis import strategies as st

import deepof.data
import deepof.utils


@settings(deadline=None)
@given(
    table_type=st.integers(min_value=0, max_value=1),
    arena_type=st.integers(min_value=0, max_value=1),
)
def test_project_init(table_type, arena_type):

    table_type = [".h5", ".csv"][table_type]
    arena_type = ["circular-autodetect", "foo"][arena_type]

    if arena_type == "foo":
        with pytest.raises(NotImplementedError):
            prun = deepof.data.Project(
                path=os.path.join(".", "tests", "test_examples", "test_single_topview"),
                arena=arena_type,
                video_scale=380,
                video_format=".mp4",
                table_format=table_type,
            ).run()
    else:
        prun = deepof.data.Project(
            path=os.path.join(".", "tests", "test_examples", "test_single_topview"),
            arena=arena_type,
            video_scale=380,
            video_format=".mp4",
            table_format=table_type,
        )

    if table_type != ".foo" and arena_type != "foo":

        assert isinstance(prun, deepof.data.Project)
        assert isinstance(prun.load_tables(verbose=True), tuple)


def test_project_properties():

    prun = deepof.data.Project(
        path=os.path.join(".", "tests", "test_examples", "test_single_topview"),
        arena="circular-autodetect",
        video_scale=380,
        video_format=".mp4",
        table_format=".h5",
    )

    assert prun.distances == "all"
    prun.distances = "testing"
    assert prun.distances == "testing"

    assert not prun.ego
    prun.ego = "testing"
    assert prun.ego == "testing"

    assert prun.angles
    prun.angles = False
    assert not prun.angles


@settings(deadline=None)
@given(
    nodes=st.integers(min_value=0, max_value=1),
    ego=st.integers(min_value=0, max_value=2),
)
def test_get_distances(nodes, ego):

    nodes = ["all", ["Center", "Nose", "Tail_base"]][nodes]
    ego = [False, "Center", "Nose"][ego]

    prun = deepof.data.Project(
        path=os.path.join(".", "tests", "test_examples", "test_single_topview"),
        arena="circular-autodetect",
        video_scale=380,
        video_format=".mp4",
        table_format=".h5",
    )
    tables, _ = prun.load_tables(verbose=True)
    prun.scales, prun.arena_params, prun.video_resolution = prun.get_arena(
        tables=tables
    )
    prun.distances = nodes
    prun.ego = ego
    prun = prun.get_distances(prun.load_tables()[0], verbose=True)

    assert isinstance(prun, dict)


@settings(deadline=None)
@given(
    nodes=st.integers(min_value=0, max_value=1),
    ego=st.integers(min_value=0, max_value=2),
)
def test_get_angles(nodes, ego):

    nodes = ["all", ["Center", "Nose", "Tail_base"]][nodes]
    ego = [False, "Center", "Nose"][ego]

    prun = deepof.data.Project(
        path=os.path.join(".", "tests", "test_examples", "test_single_topview"),
        arena="circular-autodetect",
        video_scale=380,
        video_format=".mp4",
        table_format=".h5",
    )

    prun.distances = nodes
    prun.ego = ego
    prun = prun.get_angles(prun.load_tables()[0], verbose=True)

    assert isinstance(prun, dict)


@settings(deadline=None)
@given(
    nodes=st.integers(min_value=0, max_value=1),
    ego=st.integers(min_value=0, max_value=2),
)
def test_run(nodes, ego):

    nodes = ["all", ["Center", "Nose", "Tail_base"]][nodes]
    ego = [False, "Center", "Nose"][ego]

    prun = deepof.data.Project(
        path=os.path.join(".", "tests", "test_examples", "test_single_topview"),
        arena="circular-autodetect",
        video_scale=380,
        video_format=".mp4",
        table_format=".h5",
    )

    prun.distances = nodes
    prun.ego = ego
    prun = prun.run(verbose=True)

    assert isinstance(prun, deepof.data.Coordinates)


def test_get_supervised_annotation():

    prun = deepof.data.Project(
        path=os.path.join(".", "tests", "test_examples", "test_multi_topview"),
        arena="circular-autodetect",
        video_scale=380,
        animal_ids=["B", "W"],
        video_format=".mp4",
        table_format=".h5",
    ).run()

    prun = prun.supervised_annotation()

    assert isinstance(prun, deepof.data.TableDict)
    assert prun._type == "supervised"


@settings(max_examples=36, deadline=None, derandomize=True)
@given(
    nodes=st.integers(min_value=0, max_value=1),
    mode=st.one_of(st.just("single"), st.just("multi"), st.just("madlc")),
    ego=st.integers(min_value=0, max_value=1),
    exclude=st.one_of(st.just(tuple([""])), st.just(["Tail_base"])),
    sampler=st.data(),
)
def test_get_table_dicts(nodes, mode, ego, exclude, sampler):

    nodes = ["all", ["Center", "Nose", "Tail_base"]][nodes]
    ego = [False, "Center", "Nose"][ego]

    if mode == "multi":
        animal_ids = ["B", "W"]
    elif mode == "madlc":
        animal_ids = ["mouse_black_tail", "mouse_white_tail"]
    else:
        animal_ids = [""]

    prun = deepof.data.Project(
        path=os.path.join(
            ".", "tests", "test_examples", "test_{}_topview".format(mode)
        ),
        arena="circular-autodetect",
        video_scale=380,
        video_format=".mp4",
        animal_ids=animal_ids,
        table_format=".h5",
        exclude_bodyparts=exclude,
        exp_conditions={"test": "test_cond", "test2": "test_cond"},
    )

    if mode == "single":
        prun.distances = nodes
        prun.ego = ego

    prun = prun.run(verbose=False)

    center = sampler.draw(st.one_of(st.just("arena"), st.just("Center")))
    algn = sampler.draw(st.one_of(st.just(False), st.just("Spine_1")))
    polar = st.one_of(st.just(True), st.just(False))
    speed = sampler.draw(st.integers(min_value=1, max_value=3))
    propagate = sampler.draw(st.booleans())
    propagate_annots = False
    # if exclude == tuple([""]) and nodes == "all" and not ego:
    #     propagate_annots = sampler.draw(
    #         st.one_of(st.just(prun.supervised_annotation()), st.just(False))
    #     )

    selected_id = None
    if mode == "multi" and nodes == "all" and not ego:
        selected_id = "B"
    elif mode == "madlc" and nodes == "all" and not ego:
        selected_id = "mouse_black_tail"

    coords = prun.get_coords(
        center=center,
        polar=polar,
        align=(algn if center == "Center" and not polar else False),
        propagate_labels=propagate,
        propagate_annotations=propagate_annots,
        selected_id=selected_id,
    )
    speeds = prun.get_coords(
        speed=(speed if not ego and nodes == "all" else 0),
        propagate_labels=propagate,
        selected_id=selected_id,
    )
    distances = prun.get_distances(
        speed=sampler.draw(st.integers(min_value=0, max_value=2)),
        propagate_labels=propagate,
        selected_id=selected_id,
    )
    angles = prun.get_angles(
        degrees=sampler.draw(st.booleans()),
        speed=sampler.draw(st.integers(min_value=0, max_value=2)),
        propagate_labels=propagate,
        selected_id=selected_id,
    )
   # areas = prun.get_areas()

    # deepof.coordinates testing

    assert isinstance(coords, deepof.data.TableDict)
    assert isinstance(speeds, deepof.data.TableDict)
    assert isinstance(distances, deepof.data.TableDict)
    assert isinstance(angles, deepof.data.TableDict)
   # assert isinstance(areas, deepof.data.TableDict)
    assert isinstance(prun.get_videos(), list)
    assert prun.get_exp_conditions is not None
    assert isinstance(prun.get_quality(), defaultdict)
    assert isinstance(prun.get_arenas, tuple)

    # deepof.table_dict testing

    if not propagate_annots:
        table = sampler.draw(
            st.one_of(
                st.just(coords), st.just(speeds), st.just(distances), st.just(angles)
            ),
            st.just(coords.merge(speeds, distances, angles)),
        )
    else:
        table = sampler.draw(
            st.one_of(
                st.just(coords), st.just(speeds), st.just(distances), st.just(angles)
            )
        )

    assert len(list(table.filter_videos(["test"]).keys())) == 1

    prep = table.preprocess(
        window_size=11,
        window_step=1,
        automatic_changepoints=(
            False if not any([propagate_annots, propagate]) else "linear"
        ),
        scale=sampler.draw(st.one_of(st.just("standard"), st.just("minmax"))),
        test_videos=1,
        verbose=2,
        filter_low_variance=1e-3 * (not any([propagate_annots, propagate])),
        interpolate_normalized=5 * (not any([propagate_annots, propagate])),
        shuffle=sampler.draw(st.booleans()),
    )

    assert isinstance(prep[0], np.ndarray)

    # deepof dimensionality reduction testing

    assert isinstance(table.random_projection(n_components=2), tuple)
    assert isinstance(table.pca(n_components=2), tuple)
    assert isinstance(table.tsne(n_components=2), tuple)
