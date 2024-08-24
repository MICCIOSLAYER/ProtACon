"""
Copyright (c) 2024 Simone Chiarella

Author: S. Chiarella

__main__.py file for command line application.

"""
import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from ProtACon import config_parser
from ProtACon.modules.miscellaneous import (
    all_amino_acids,
    get_model_structure,
    load_model,
)
from ProtACon.modules.utils import (
    Loading,
    Timer,
)
from ProtACon import align_with_contact
from ProtACon import average_on_set
from ProtACon import plotting
from ProtACon import preprocess


def parse_args():
    """Argument parser."""
    description = "ProtACon"
    parser = argparse.ArgumentParser(description=description)

    subparsers = parser.add_subparsers(
        dest="subparser",
        help="possible actions",
    )

    # on_set parser
    on_set = subparsers.add_parser(
        "on_set",
        help="get attention alignment and other quantities averaged over a set"
        " of peptide chains",
    )
    # optional arguments
    on_set.add_argument(
        "-s", "--save_single",
        action='store_true',
        help="save all plots relative to each single peptide chain",
    )

    # on_chain parser
    on_chain = subparsers.add_parser(
        "on_chain",
        help="get attention alignment and other quantities for one single "
        "peptide chain",
    )
    # positional arguments
    on_chain.add_argument(
        "chain_code",
        type=str,
        help="code of the input peptide chain",
    )

    # 3d_viz parser
    net_viz = subparsers.add_parser(
        "net_viz",
        help="visualize 3D network of a protein with one selected property "
        "and the attention alignment of that property",
    )
    # positional arguments
    net_viz.add_argument(
        "chain_code",
        type=str,
        help="code of the input peptide chain",
    )
    net_viz.add_argument(
        "property",
        type=str,
        help="property or network to show",
    )

    args = parser.parse_args()
    return args


def main():
    """Run the script chosen by the user."""
    args = parse_args()

    logging.basicConfig(format='%(message)s', level=logging.INFO)
    config = config_parser.Config("config.txt")

    paths = config.get_paths()
    plot_folder = paths["PLOT_FOLDER"]
    plot_dir = Path(__file__).resolve().parents[1]/plot_folder

    model_name = "Rostlab/prot_bert"
    with Loading("Loading the model"):
        model, tokenizer = load_model(model_name)

    if args.subparser == "on_set":
        proteins = config.get_proteins()
        protein_codes = proteins["PROTEIN_CODES"].split(" ")

        with Timer("Total running time"):
            for code_idx, code in enumerate(protein_codes):
                with Timer(f"Running time for {code}") and torch.no_grad():

                    logging.info(f"Protein n.{code_idx+1}: {code}")
                    attention, CA_Atoms, chain_amino_acids, \
                        att_to_amino_acids = preprocess.main(
                            code, model, tokenizer
                        )
                    
                    number_of_heads, number_of_layers = get_model_structure(
                        attention
                    )

                    # istantiate the variables to store the sum of the
                    # quantities to average over the set of proteins later
                    if code_idx == 0:
                        sum_rel_att_to_am_ac = torch.zeros(
                            (
                                len(all_amino_acids),
                                number_of_layers,
                                number_of_heads
                            ), dtype=float
                        )
                        sum_weight_att_to_am_ac = torch.zeros(
                            (
                                len(all_amino_acids),
                                number_of_layers,
                                number_of_heads
                            ), dtype=float
                        )
                        sum_att_sim_df = pd.DataFrame(
                            data=0., index=all_amino_acids,
                            columns=all_amino_acids
                        )
                        sum_head_att_align = np.zeros(
                            (number_of_layers, number_of_heads), dtype=float
                        )
                        sum_layer_att_align = np.zeros(
                            number_of_layers, dtype=float
                        )

                    if args.save_single:
                        att_sim_df, head_att_align, layer_att_align = \
                            align_with_contact.main(
                                attention, CA_Atoms, chain_amino_acids,
                                att_to_amino_acids[0], code, args.save_single
                            )
                    else:
                        att_sim_df, head_att_align, layer_att_align = \
                            align_with_contact.main(
                                attention, CA_Atoms, chain_amino_acids,
                                att_to_amino_acids[0], code
                            )

                    # sum all the quantities
                    sum_rel_att_to_am_ac = torch.add(
                        sum_rel_att_to_am_ac, att_to_amino_acids[1]
                    )
                    sum_weight_att_to_am_ac = torch.add(
                        sum_weight_att_to_am_ac, att_to_amino_acids[2]
                    )
                    sum_att_sim_df = sum_att_sim_df.add(
                        att_sim_df, fill_value=0
                    )
                    sum_head_att_align = np.add(
                        sum_head_att_align, head_att_align
                    )
                    sum_layer_att_align = np.add(
                        sum_layer_att_align, layer_att_align)

            avg_P_att_to_am_ac, avg_PW_att_to_am_ac, avg_att_sim_df, \
                avg_head_att_align, avg_layer_att_align = average_on_set.main(
                    sum_rel_att_to_am_ac,
                    sum_weight_att_to_am_ac,
                    sum_att_sim_df,
                    sum_head_att_align,
                    sum_layer_att_align,
                    len(protein_codes)
                )

            plotting.plot_on_set(
                avg_P_att_to_am_ac,
                avg_PW_att_to_am_ac,
                avg_att_sim_df,
                avg_head_att_align,
                avg_layer_att_align,
                all_amino_acids
            )

    if (args.subparser == "on_chain" or args.subparser == "net_viz"):
        seq_dir = plot_dir/args.chain_code
        seq_dir.mkdir(parents=True, exist_ok=True)

    if args.subparser == "on_chain":
        with Timer(f"Running time for {args.chain_code}"),  torch.no_grad():

            attention, CA_Atoms, chain_amino_acids, att_to_amino_acids = \
                preprocess.main(args.chain_code, model, tokenizer)

            att_sim_df, head_att_align, layer_att_align = \
                align_with_contact.main(
                    attention, CA_Atoms, chain_amino_acids,
                    att_to_amino_acids[0], args.chain_code, save_single=True
                )


if __name__ == '__main__':
    main()
