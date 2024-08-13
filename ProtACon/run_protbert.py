"""
Copyright (c) 2024 Simone Chiarella

Author: S. Chiarella

Run ProtBert on the peptide chain and return the tokens and the attention.

"""
from __future__ import annotations

from typing import TYPE_CHECKING

import torch

from ProtACon.modules.miscellaneous import (
    extract_CA_Atoms,
    get_sequence_to_tokenize,
    load_model,
)
from ProtACon.modules.utils import read_pdb_file

if TYPE_CHECKING:
    from ProtACon.modules.miscellaneous import CA_Atom


def main(
    seq_ID: str,
) -> tuple[
    tuple[torch.Tensor, ...],
    list[str],
    tuple[CA_Atom, ...],
]:
    """
    Run ProtBert on one peptide chain.

    The peptide chain is identified with its seq_ID. The function returns the
    tokens and the attention extracted from ProtBert.

    Parameters
    ----------
    seq_ID : str
        The alphanumerical code representing uniquely the peptide chain.

    Returns
    -------
    raw_attention : tuple[torch.Tensor, ...]
        The attention from the model, including the attention relative to
        tokens [CLS] and [SEP].
    raw_tokens : list[str]
        The tokens used by the model, including the tokens [CLS] and [SEP].
    CA_Atoms: tuple[CA_Atom, ...]

    """
    model = load_model.model
    tokenizer = load_model.tokenizer
    structure = read_pdb_file(seq_ID)
    CA_Atoms = extract_CA_Atoms(structure)
    sequence = get_sequence_to_tokenize(CA_Atoms)

    encoded_input = tokenizer.encode(sequence, return_tensors='pt')
    output = model(encoded_input)

    raw_tokens = tokenizer.convert_ids_to_tokens(encoded_input[0])
    raw_attention = output[-1]

    return (
        raw_attention,
        raw_tokens,
        CA_Atoms,
    )
