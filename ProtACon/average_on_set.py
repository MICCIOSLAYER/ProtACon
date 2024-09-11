"""
Copyright (c) 2024 Simone Chiarella

Author: S. Chiarella
Date: 2024-08-14

Compute and save the averages of:

- the percentage of the attention given to each amino acid
- the percentage of the attention given to each amino acid, weighted by the
  occurrences of that amino acid in the chain
- the attention similarity
- the attention-contact alignment in the attention heads
- the attention-contact alignment across the layers

"""
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from ProtACon import config_parser
from ProtACon.modules.utils import Loading


def main(
    sum_rel_att_to_am_ac: torch.Tensor,
    sum_weight_att_to_am_ac: torch.Tensor,
    sum_att_sim_df: pd.DataFrame,
    sum_head_att_align_list: np.ndarray,
    sum_layer_att_align_list: np.ndarray,
    number_of_samples: int,
) -> tuple[
    torch.Tensor,
    torch.Tensor,
    np.ndarray,
    np.ndarray,
    np.ndarray,
]:
    """
    Compute attention alignment and similarity over the whole set of proteins.

    Parameters
    ----------
    sum_rel_att_to_am_ac : torch.Tensor
        Tensor with shape (number_of_amino_acids, number_of_layers,
        number_of_heads), storing the sum over the set of proteins of the
        relative attention in percentage given to each amino acid by each
        attention head; "rel" (relative) means that the values of attention
        given by one head to one amino acid are divided by the total value of
        attention of that head.
    sum_weight_att_to_am_ac : torch.Tensor
        The tensor resulting from weighting sum_rel_att_to_amino_acids by the
        number of occurrences of the corresponding amino acid.
    sum_att_sim_df : pd.DataFrame
        The sum over the set of proteins of the attention similarity data
        frames between each couple of amino acids for each peptide chain.
    sum_head_att_align_list : np.ndarray
        The sum over the set of proteins of the arrays, each one with shape
        (number_of_layers, number_of_heads), storing how much attention aligns
        with indicator_function for each attention matrix.
    sum_layer_att_align_list : np.ndarray
        The sum over the set of proteins of the arrays, each one with shape
        (number_of_layers), storing how much attention aligns with
        indicator_function for each average attention matrix computed
        independently over each layer.
    number_of_samples : int
        The number of proteins in the set.

    Returns
    -------
    avg_P_att_to_amino_acids : torch.Tensor
        The percentage of attention given to each amino acid by each attention
        head, averaged over the whole protein set.
    avg_PW_att_to_amino_acids : torch.Tensor
        The percentage of weighted attention given to each amino acid by each
        attention head, averaged over the whole protein set.
    avg_att_sim_arr : np.ndarray
        The attention similarity averaged over the whole protein set.
    avg_head_att_align : np.ndarray
        The head attention alignment averaged over the whole protein set.
    avg_layer_att_align : np.ndarray
        The layer attention alignment averaged over the whole protein set.

    """
    config = config_parser.Config("config.txt")
    paths = config.get_paths()

    file_folder = paths["FILE_FOLDER"]
    file_dir = Path(__file__).resolve().parents[1]/file_folder

    with Loading("Saving average percentage of attention to amino acids"):
        avg_P_att_to_amino_acids = sum_rel_att_to_am_ac/number_of_samples*100
        torch.save(
            avg_P_att_to_amino_acids, file_dir/"avg_P_att_to_amino_acids.pt"
        )

    with Loading(
        "Saving average percentage of weighted attention to amino acids"
    ):
        avg_PW_att_to_amino_acids = \
            sum_weight_att_to_am_ac/number_of_samples*100
        torch.save(
            avg_PW_att_to_amino_acids, file_dir/"avg_PW_att_to_amino_acids.pt"
        )

    with Loading("Saving average attention similarity"):
        avg_att_sim_df = sum_att_sim_df.div(number_of_samples)
        # set diagonal to NaN
        avg_att_sim_arr = avg_att_sim_df.to_numpy()
        np.fill_diagonal(avg_att_sim_arr, np.nan)
        avg_att_sim_df.to_csv(
            file_dir/"attention_sim_df.csv", index=True, sep=';'
        )

    with Loading("Saving average head attention alignment"):
        avg_head_att_align = sum_head_att_align_list/number_of_samples
        np.save(file_dir/"avg_head_att_align.npy", avg_head_att_align)

    with Loading("Saving average layer attention alignment"):
        avg_layer_att_align = sum_layer_att_align_list/number_of_samples
        np.save(file_dir/"avg_layer_att_align.npy", avg_layer_att_align)

    return (
        avg_P_att_to_amino_acids,
        avg_PW_att_to_amino_acids,
        avg_att_sim_arr,
        avg_head_att_align,
        avg_layer_att_align,
    )
