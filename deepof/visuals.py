# @author lucasmiranda42
# encoding: utf-8
# module deepof

"""

General plotting functions for the deepof package

"""

from itertools import cycle
from matplotlib.animation import FuncAnimation, FFMpegWriter
from matplotlib.colors import ListedColormap
from matplotlib.patches import Ellipse
from typing import Any, List, NewType, Union

import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import warnings


# DEFINE CUSTOM ANNOTATED TYPES #
project = NewType("deepof_project", Any)
coordinates = NewType("deepof_coordinates", Any)
table_dict = NewType("deepof_table_dict", Any)


# PLOTTING FUNCTIONS #


def plot_arena(
    coordinates: coordinates, center: str, color: str, ax: Any, i: Union[int, str]
):
    """Plots the arena in the given canvas.

    Args:
        coordinates: deepof Coordinates object.
        center: Name of the body part to which the positions will be centered. If false,
        the raw data is returned; if 'arena' (default), coordinates are centered in the pitch.
        color: color of the displayed arena.
        ax: axes where to plot the arena.
        i: index of the animal to plot.
    """

    if isinstance(i, np.int64):
        arena = coordinates._arena_params[i]

    if "circular" in coordinates._arena:

        if i == "average":
            arena = [
                np.mean(np.array([i[0] for i in coordinates._arena_params]), axis=0),
                np.mean(np.array([i[1] for i in coordinates._arena_params]), axis=0),
                np.mean(np.array([i[2] for i in coordinates._arena_params]), axis=0),
            ]

        ax.add_patch(
            Ellipse(
                xy=((0, 0) if center == "arena" else arena[0]),
                width=arena[1][0] * 2,
                height=arena[1][1] * 2,
                angle=arena[2],
                edgecolor=color,
                fc="None",
                lw=3,
                ls="--",
            )
        )

    elif "polygonal" in coordinates._arena:

        if center == "arena" and i == "average":
            arena = np.stack(coordinates._arena_params)
            arena -= np.expand_dims(
                np.array(coordinates._scales[:, :2]).astype(int), axis=1
            )
            arena = arena.mean(axis=0)

        elif center == "arena":
            arena -= np.expand_dims(
                np.array(coordinates._scales[i, :2]).astype(int), axis=1
            ).T

        # Repeat first element for the drawn polygon to be closed
        arena_corners = np.array(list(arena) + [arena[0]])

        ax.plot(
            *arena_corners.T,
            color=color,
            lw=3,
            ls="--",
        )


def heatmap(
    dframe: pd.DataFrame,
    bodyparts: List,
    xlim: tuple,
    ylim: tuple,
    title: str,
    save: str = False,
    dpi: int = 200,
    ax: Any = None,
    **kwargs,
) -> plt.figure:
    """Returns a heatmap of the movement of a specific bodypart in the arena.
    If more than one bodypart is passed, it returns one subplot for each.

     Args:
         dframe: table_dict value with info to plot
         bodyparts: bodyparts to represent (at least 1)
         xlim: limits of the x-axis
         ylim: limits of the y-axis
         save: if provided, saves the figure to the specified file.
         dpi: dots per inch of the figure to create.
         ax: axes where to plot the current figure. If not provided, a new figure will be created.

     Returns:
         heatmaps (plt.figure): figure with the specified characteristics
    """

    # noinspection PyTypeChecker
    if ax is None:
        heatmaps, ax = plt.subplots(
            1,
            len(bodyparts),
            sharex=True,
            sharey=True,
            dpi=dpi,
            figsize=(8 * len(bodyparts), 8),
        )

    for i, bpart in enumerate(bodyparts):
        heatmap = dframe[bpart]

        if len(bodyparts) > 1:
            sns.kdeplot(
                x=heatmap.x,
                y=heatmap.y,
                cmap="magma",
                fill=True,
                alpha=1,
                ax=ax[i],
                **kwargs,
            )
        else:
            sns.kdeplot(
                x=heatmap.x, y=heatmap.y, cmap="magma", fill=True, alpha=1, ax=ax
            )
            ax = np.array([ax])

    for x, bp in zip(ax, bodyparts):
        x.set_xlim(xlim)
        x.set_ylim(ylim)
        x.set_title(f"{bp} - {title}", fontsize=10)

    if save:  # pragma: no cover
        plt.savefig(save)

    return ax


# noinspection PyTypeChecker
def plot_heatmaps(
    coordinates: coordinates,
    bodyparts: list,
    center: str = "arena",
    align: str = None,
    exp_condition: str = None,
    display_arena: bool = True,
    xlim: float = None,
    ylim: float = None,
    save: bool = False,
    experiment_id: int = "average",
    dpi: int = 100,
    ax: Any = None,
    show: bool = True,
    **kwargs,
) -> plt.figure:  # pragma: no cover
    """Plots heatmaps of the specified body parts (bodyparts) of the specified animal (i).

    Args:
        coordinates: deepof Coordinates object.
        bodyparts: list of body parts to plot.
        center: Name of the body part to which the positions will be centered. If false,
        the raw data is returned; if 'arena' (default), coordinates are centered in the pitch.
        align: Selects the body part to which later processes will align the frames with
        (see preprocess in table_dict documentation).
        exp_condition: Experimental condition to plot. If available, it filters the experiments
        to keep only those whose condition matches the given string.
        display_arena: whether to plot a dashed line with an overlying arena perimeter. Defaults to True.
        xlim: x-axis limits.
        ylim: y-axis limits.
        save:  if provided, the figure is saved to the specified path.
        experiment_id: index of the animal to plot.
        dpi: resolution of the figure.
        ax: axes where to plot the current figure. If not provided,
        a new figure will be created.
        show: whether to show the created figure. If False, returns al axes.

    Returns:
        heatmaps (plt.figure): figure with the specified characteristics
    """

    coords = coordinates.get_coords(center=center, align=align)

    if exp_condition is not None:
        coords = coords.filter_videos(
            [k for k, v in coordinates.get_exp_conditions.items() if v == exp_condition]
        )

    if not center:  # pragma: no cover
        warnings.warn("Heatmaps look better if you center the data")

    # Add experimental conditions to title, if provided
    title_suffix = experiment_id
    if coordinates.get_exp_conditions is not None and exp_condition is None:
        title_suffix += (
            " - " + coordinates.get_exp_conditions[list(coords.keys())[experiment_id]]
        )

    elif exp_condition is not None:
        title_suffix += f" - {exp_condition}"

    if experiment_id != "average":

        i = np.argmax(np.array(list(coords.keys())) == experiment_id)
        coords = coords[experiment_id]

    else:
        i = experiment_id
        coords = pd.concat([val for val in coords.values()], axis=0).reset_index(
            drop=True
        )

    heatmaps = heatmap(
        coords,
        bodyparts,
        xlim=xlim,
        ylim=ylim,
        title=title_suffix,
        save=save,
        dpi=dpi,
        ax=ax,
        **kwargs,
    )

    if display_arena:
        for hmap in heatmaps:
            plot_arena(coordinates, center, "white", hmap, i)

    if show:
        plt.show()
    else:
        return heatmaps


def plot_embeddings(
    embeddings: np.ndarray,
    cluster_assignments: np.ndarray = None,
    ax: Any = None,
    save: str = False,
    show: bool = True,
    dpi: int = 200,
) -> plt.figure:
    """Returns a scatter plot of the passed projection. Each dot represents the trajectory of an entire animal.
      If labels are propagated, it automatically colours all data points with their respective condition.

    Args:
        embeddings: sequence embeddings obtained with the unsupervised pipeline within deepof
        cluster_assignments: labels of the clusters. If None, aggregation method should be provided.
        ax: axes where to plot the arena.
        save: if provided, saves the figure to the specified file.
        show: if True, displays the current figure. If not, returns the given axes.
        dpi: dots per inch of the figure to create.

    Returns:
        projection_scatter (plt.figure): figure with the specified characteristics
    """

    if ax is None:
        fig, ax = plt.subplots(1, 1, dpi=dpi)

    # Plot entire UMAP
    ax.scatter(
        embeddings[:, 0],
        embeddings[:, 1],
        c=(cluster_assignments if cluster_assignments is not None else None),
        cmap=("tab10" if cluster_assignments is not None else None),
    )

    plt.tight_layout()

    if save:
        plt.savefig(save)

    if not show:
        return ax

    plt.show()


# noinspection PyTypeChecker
def animate_skeleton(
    coordinates: coordinates,
    experiment_id: str,
    animal_id: list = None,
    center: str = "arena",
    align: str = None,
    frame_limit: int = None,
    cluster_assignments: np.ndarray = None,
    embedding: Union[List, np.ndarray] = None,
    selected_cluster: np.ndarray = None,
    display_arena: bool = True,
    legend: bool = True,
    save: bool = None,
    dpi: int = 300,
):
    """FuncAnimation function to plot motion trajectories over time.

    Args:
        coordinates: deepof Coordinates object.
        experiment_id: Name of the experiment to display.
        animal_id: ID list of animals to display. If None (default) it shows all animals.
        center: Name of the body part to which the positions will be centered. If false,
        the raw data is returned; if 'arena' (default), coordinates are centered in the pitch.
        align: Selects the body part to which later processes will align the frames with
        (see preprocess in table_dict documentation).
        frame_limit: Number of frames to plot. If None, the entire video is rendered.
        cluster_assignments: contain sorted cluster assignments for all instances in data.
        If provided together with selected_cluster, only instances of the specified component are returned.
        Defaults to None.
        only instances of the specified component are returned. Defaults to None.
        embedding: UMAP 2D embedding of the datapoints provided. If not None, a second animation
        shows a parallel animation showing the currently selected embedding, colored by cluster if cluster_assignments
        are available.
        selected_cluster: cluster to filter. If provided together with cluster_assignments,
        display_arena: whether to plot a dashed line with an overlying arena perimeter. Defaults to True.
        legend: whether to add a color-coded legend to multi-animal plots. Defaults to True when there are more
        than one animal in the representation, False otherwise.
        save: name of the file where to save the produced animation.
        dpi: dots per inch of the figure to create.
    """

    # Get data to plot from coordinates object
    data = coordinates.get_coords(center=center, align=align)

    # Filter requested animals
    if experiment_id is not None:
        data = data.filter_id(animal_id)

    # Select requested experiment and frames
    data = data[experiment_id]

    # Checks that all shapes and passed parameters are correct
    if embedding is not None:

        if isinstance(embedding, np.ndarray):
            assert (
                embedding.shape[0] == data.shape[0]
            ), "there should be one embedding per row in data"

            concat_embedding = embedding
            embedding = [embedding]

        elif isinstance(embedding, list):

            assert len(embedding) == len(coordinates._animal_ids)

            for emb in embedding:
                assert (
                    emb.shape[0] == data.shape[0]
                ), "there should be one embedding per row in data"

            concat_embedding = np.concatenate(embedding)

        if selected_cluster is not None:
            cluster_embedding = embedding[cluster_assignments == selected_cluster]

        else:
            cluster_embedding = embedding

    if cluster_assignments is not None:

        assert (
            len(cluster_assignments) == data.shape[0]
        ), "there should be one cluster assignment per row in data"

        # Filter data to keep only those instances assigned to a given cluster
        if selected_cluster is not None:

            assert selected_cluster in set(
                cluster_assignments
            ), "selected cluster should be in the clusters provided"

            data = data.loc[cluster_assignments == selected_cluster, :]

    # Sort column index to allow for multiindex slicing
    data = data.sort_index(ascending=True, inplace=False, axis=1)

    def get_polygon_coords(data, animal_id=None):
        """Generates polygons to animate for the indicated animal in the provided dataframe."""

        if animal_id is not None:
            animal_id += "_"

        head = np.concatenate(
            [
                data.xs(f"{animal_id}Nose", 1).values,
                data.xs(f"{animal_id}Left_ear", 1).values,
                data.xs(f"{animal_id}Spine_1", 1).values,
                data.xs(f"{animal_id}Right_ear", 1).values,
            ],
            axis=1,
        )

        body = np.concatenate(
            [
                data.xs(f"{animal_id}Spine_1", 1).values,
                data.xs(f"{animal_id}Left_fhip", 1).values,
                data.xs(f"{animal_id}Left_bhip", 1).values,
                data.xs(f"{animal_id}Spine_2", 1).values,
                data.xs(f"{animal_id}Right_bhip", 1).values,
                data.xs(f"{animal_id}Right_fhip", 1).values,
            ],
            axis=1,
        )

        tail = np.concatenate(
            [
                data.xs(f"{animal_id}Spine_2", 1).values,
                data.xs(f"{animal_id}Tail_base", 1).values,
            ],
            axis=1,
        )

        return [head, body, tail]

    # Define canvas
    fig = plt.figure(figsize=((16 if embedding is not None else 8), 8), dpi=dpi)

    # If embeddings are provided, add projection plot to the left
    if embedding is not None:
        ax1 = fig.add_subplot(121)

        plot_embeddings(concat_embedding, cluster_assignments, ax1, show=False)

        # Plot current position
        umap_scatter = {}
        for i, emb in enumerate(embedding):
            umap_scatter[i] = ax1.scatter(
                emb[0, 0],
                emb[0, 1],
                color=(
                    "red"
                    if len(embedding) == 1
                    else list(sns.color_palette("tab10"))[i]
                ),
                s=200,
                linewidths=2,
                edgecolors="black",
            )

        ax1.set_title("UMAP projection of time embedding", fontsize=15)
        ax1.set_xlabel("UMAP-1")
        ax1.set_ylabel("UMAP-2")

    # Add skeleton animation
    ax2 = fig.add_subplot((122 if embedding is not None else 111))

    # Plot!
    init_x = data.loc[:, (slice("x"), ["x"])].iloc[0, :]
    init_y = data.loc[:, (slice("x"), ["y"])].iloc[0, :]

    # If there are more than one animal in the representation, display each in a different color
    hue = None
    cmap = ListedColormap(sns.color_palette("tab10", len(coordinates._animal_ids)))

    if animal_id is None:
        animal_ids = coordinates._animal_ids
    else:
        animal_ids = [animal_id]

    polygons = [get_polygon_coords(data, aid) for aid in animal_ids]

    if animal_id is None:
        hue = np.zeros(len(np.array(init_x)))
        for i, id in enumerate(coordinates._animal_ids):

            hue[data.columns.levels[0].str.startswith(id)] = i

            # Set a custom legend outside the plot, with the color of each animal

            if legend:
                custom_labels = [
                    plt.scatter(
                        [np.inf],
                        [np.inf],
                        color=cmap(i / len(coordinates._animal_ids)),
                        lw=3,
                    )
                    for i in range(len(coordinates._animal_ids))
                ]
                ax2.legend(custom_labels, coordinates._animal_ids, loc="upper right")

    skeleton_scatter = ax2.scatter(
        x=np.array(init_x),
        y=np.array(init_y),
        cmap=(cmap if animal_id is None else None),
        label="Original",
        c=hue,
    )

    tail_lines = []
    for p, aid in enumerate(polygons):
        ax2.add_patch(
            patches.Polygon(
                aid[0][0, :].reshape(-1, 2),
                closed=True,
                fc=cmap.colors[p],
                ec=cmap.colors[p],
                alpha=0.5,
            )
        )
        ax2.add_patch(
            patches.Polygon(
                aid[1][0, :].reshape(-1, 2),
                closed=True,
                fc=cmap.colors[p],
                ec=cmap.colors[p],
                alpha=0.5,
            )
        )
        tail_lines.append(ax2.plot(*aid[2][0, :].reshape(-1, 2).T))

    if display_arena and center in [False, "arena"] and align is None:
        i = np.argmax(np.array(list(coordinates.get_coords().keys())) == experiment_id)
        plot_arena(coordinates, center, "black", ax2, i)

    # Update data in main plot
    def animation_frame(i):

        if embedding is not None:
            # Update umap scatter
            for j, xy in umap_scatter.items():
                umap_x = cluster_embedding[j][i, 0]
                umap_y = cluster_embedding[j][i, 1]

                umap_scatter[j].set_offsets(np.c_[umap_x, umap_y])

        # Update skeleton scatter plot
        x = data.loc[:, (slice("x"), ["x"])].iloc[i, :]
        y = data.loc[:, (slice("x"), ["y"])].iloc[i, :]

        skeleton_scatter.set_offsets(np.c_[x, y])

        for p, aid in enumerate(polygons):
            # Update polygons
            ax2.patches[2 * p].set_xy(aid[0][i, :].reshape(-1, 2))
            ax2.patches[2 * p + 1].set_xy(aid[1][i, :].reshape(-1, 2))

            # Update tails
            tail_lines[p][0].set_xdata(aid[2][i, :].reshape(-1, 2)[:, 0])
            tail_lines[p][0].set_ydata(aid[2][i, :].reshape(-1, 2)[:, 1])

        if embedding is not None:
            return umap_scatter, skeleton_scatter

        return skeleton_scatter

    animation = FuncAnimation(
        fig,
        func=animation_frame,
        frames=np.minimum(data.shape[0], frame_limit),
        interval=50,
    )

    ax2.set_title(
        f"deepOF animation - {(f'{animal_id} - ' if animal_id is not None else '')}{experiment_id}",
        fontsize=15,
    )
    ax2.set_xlabel("x")
    ax2.set_ylabel("y")

    if center not in [False, "arena"]:

        x_dv = np.maximum(
            np.abs(data.loc[:, (slice("x"), ["x"])].min().min()),
            np.abs(data.loc[:, (slice("x"), ["x"])].max().max()),
        )
        y_dv = np.maximum(
            np.abs(data.loc[:, (slice("x"), ["y"])].min().min()),
            np.abs(data.loc[:, (slice("x"), ["y"])].max().max()),
        )

        ax2.set_xlim(-1.5 * x_dv, 1.5 * x_dv)
        ax2.set_ylim(-1.5 * y_dv, 1.5 * y_dv)

    plt.tight_layout()

    if save is not None:
        writevideo = FFMpegWriter(fps=15)
        animation.save(save, writer=writevideo)

    return animation.to_html5_video()
