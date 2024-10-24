"""
Copyright (c) 2024 Simone Chiarella

Author: S. Chiarella, R. Eliasy

__main__.py file for command line application.

"""
import argparse
from pathlib import Path

import numpy as np
import torch

from ProtACon import config_parser
from ProtACon.modules.attention import compute_attention_alignment
from ProtACon.modules.miscellaneous import (
    fetch_pdb_entries,
    get_model_structure,
    load_model,
)
from ProtACon.modules.plot_functions import plot_heatmap
from ProtACon.modules.utils import (
    Logger,
    Loading,
    Timer,
)
from ProtACon import align_with_contact
from ProtACon import compute_on_set
from ProtACon import manage_tot_ds
from ProtACon import plotting
from ProtACon import preprocess
from ProtACon import process_instability
from ProtACon.modules.on_network import summarize_results_for_main as sum_up
from ProtACon.modules.on_network import PCA_computing_and_results, Collect_and_structure_data
from ProtACon import network_vizualization as netviz
from ProtACon.modules.on_network import kmeans_computing_and_results as km
import matplotlib.pyplot as plt


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
        help="get the attention alignment with one of the positional"
        " arguments for a set of peptide chains",
    )
    # positional arguments
    on_set.add_argument(
        "align_with",
        type=str,
        choices=["contact", "instability", "kmeans", "louvain"],
        help="get the attention alignment with the contact map, the "
        "instability index, the clusters found with the k-means algorithm, or "
        "the communities found with the Louvain mehtod",
    )
    # optional arguments
    on_set.add_argument(
        "-s", "--save_every",
        default="none",  # if the flag is not present
        const="both",  # if the flag is present but no arguments are given
        nargs="?",
        choices=("none", "plot", "csv", "both"),
        help="save plots and/or csv files relative to each single peptide "
        "chain; if no arguments are given, both plots and csv files are saved",
    )
    on_set.add_argument(
        "-v", "--verbose",
        action="count",
        default=0,
        help="verbose output: (-v) print info about the chain composition and "
        "the performed steps (-vv) for debugging",
    )

    # on_chain parser
    on_chain = subparsers.add_parser(
        "on_chain",
        help="get the attention alignment with one of the positional "
        "arguments for one peptide chain",
    )
    # positional arguments
    on_chain.add_argument(
        "chain_code",
        type=str,
        help="code of the input peptide chain",
    )
    on_chain.add_argument(
        "align_with",
        type=str,
        choices=["contact", "instability", "kmeans", "louvain"],
        help="get the attention alignment with the contact map, the "
        "instability index, the clusters found with the k-means algorithm, or "
        "the communities found with the Louvain mehtod",
    )
    # positional NOTE to further informations see commit 7d90661
    on_chain.add_argument(
        "plot_type",
        type=str,
        choices=["chain3D", "pca", "network"],
        help="type of plot to visualize",
    )
    """# optional
    visualize.add_argument(
        "-r", "--print_results",
        action="store_true",
        help='decide if to visualize also the results of the analysis, '
        'both for the attention alignment, PCAs, and V-measure',
    )
    """
    # positional
    on_chain.add_argument(
        "analyze",
        type=str,
        choices=["louvain", "kmeans", "both", "only_pca"],
        help="type of analysis to visualize the results on",
    )
    # increase option
    on_chain.add_argument(
        "-nc", "--node_color",
        type=str,
        default="ph_local",
        choices=["ph_local", "ph_single", "charge", "flexy", "iso_ph"],
        help="color of the nodes in the plots",
    )
    on_chain.add_argument(
        "-ec", "--edge_color",
        type=str,
        default="instability",
        choices=["instability", "proximity", "sequence_adjancency"],
        help="color of the edges in the plots",
    )
    on_chain.add_argument(
        "-es", "--edge_style",
        type=str,
        default="sequence_adjancency",
        choices=["instability", "proximity", "sequence_adjancency"],
    )
    on_chain.add_argument(
        "-ns", "--node_size",
        type=str,
        default="volume",
        choices=["charge", "radius_of_gyration", "surface", "volume"],
        help="size of the nodes in the plots",
    )
    # optional arguments
    on_chain.add_argument(
        "-v", "--verbose",
        action="count",
        default=0,
        help="verbose output: (-v) print info about the chain composition and "
        "the performed steps (-vv) for debugging",
    )

    test_this = subparsers.add_parser(
        "test_this",
        help="test this feature",
    )
    test_this.add_argument(
        '-v', '--verbose',
        action='count',
        default=0,
        help='verbose output: nothing special'
    )

    test_this.add_argument(
        '--testing',
        type=str,
        help='execute a certain set of instruction to test their correct functioning'
    )

    args = parser.parse_args()

    return args


def main():
    """Run the script chosen by the user."""
    args = parse_args()

    log = Logger(name="mylog", verbosity=args.verbose)

    config_file_path = Path(__file__).resolve().parents[1]/"config.txt"
    config = config_parser.Config(config_file_path)

    paths = config.get_paths()
    file_folder = paths["FILE_FOLDER"]
    plot_folder = paths["PLOT_FOLDER"]
    test_folder = paths["TEST_FOLDER"]

    file_dir = Path(__file__).resolve().parents[1]/file_folder
    plot_dir = Path(__file__).resolve().parents[1]/plot_folder
    test_dir = Path(__file__).resolve().parents[1]/test_folder

    file_dir.mkdir(parents=True, exist_ok=True)
    plot_dir.mkdir(parents=True, exist_ok=True)
    test_dir.mkdir(parents=True, exist_ok=True)

    model_name = "Rostlab/prot_bert"
    with Loading("Loading the model"):
        model, tokenizer = load_model(model_name)

    if args.subparser == "on_set":
        proteins = config.get_proteins()
        protein_codes = proteins["PROTEIN_CODES"].split(" ")

        if protein_codes[0] == '':
            # i.e., if PROTEIN_CODES is not provided in the configuration file
            min_length = proteins["MIN_LENGTH"]
            max_length = proteins["MAX_LENGTH"]
            sample_size = proteins["SAMPLE_SIZE"]
            protein_codes = fetch_pdb_entries(
                min_length=min_length,
                max_length=max_length,
                n_results=sample_size,
                stricter_search=False,
            )
            protein_codes_file = file_dir/"protein_codes.txt"
            with open(protein_codes_file, "w") as f:
                f.write(" ".join(protein_codes))
                log.logger.info(f"Protein codes saved to {protein_codes_file}")

        with Timer("Total running time"):
            for code_idx, code in enumerate(protein_codes):
                with (
                    Timer(f"Running time for [yellow]{code}[/yellow]"),
                    torch.no_grad(),
                ):
                    log.logger.info(f"Protein n.{code_idx+1}: [yellow]{code}")
                    attention, att_head_sum, CA_Atoms, amino_acid_df, \
                        att_to_aa = preprocess.main(
                            code, model, tokenizer, args.save_every
                        )
                    log.logger.info(
                        f"Actual number of residues: {len(CA_Atoms)}"
                    )

                    chain_amino_acids = amino_acid_df["Amino Acid"].to_list()
                    skips = 0

                    if args.align_with == "contact":
                        min_residues = 10
                        if len(CA_Atoms) < min_residues:
                            log.logger.warning(
                                f"Chain {code} has less than {min_residues} "
                                "valid residues... Skipping"
                            )
                            skips += 1
                            # delete the code from protein_codes.txt
                            with open(protein_codes_file, "r") as file:
                                filedata = file.read()
                            filedata = filedata.replace(code+" ", "")
                            with open(protein_codes_file, "w") as file:
                                file.write(filedata)
                            continue

                        binary_contact_map, head_att_align, layer_att_align, max_head_att_align = \
                            align_with_contact.main(
                                attention, CA_Atoms, chain_amino_acids,
                                att_to_aa, code, args.save_every
                            )

                        chain_ds = (
                            amino_acid_df,
                            att_head_sum,
                            att_to_aa,
                            head_att_align,
                            layer_att_align,
                            max_head_att_align,
                        )

                        # instantiate the data structures to store the sum of
                        # the quantities to average over the set of proteins
                        # later
                        if code_idx == 0:
                            n_heads, n_layers = get_model_structure(attention)
                            tot_amino_acid_df, tot_att_head_sum, \
                                tot_att_to_aa, tot_head_att_align, \
                                tot_layer_att_align, tot_max_head_att_align = \
                                manage_tot_ds.create(
                                    n_layers, n_heads
                                )

                        # sum all the quantities
                        tot_amino_acid_df, tot_att_head_sum, tot_att_to_aa, \
                            tot_head_att_align, tot_layer_att_align, \
                            tot_max_head_att_align = manage_tot_ds.update(
                                tot_amino_acid_df,
                                tot_att_head_sum,
                                tot_att_to_aa,
                                tot_head_att_align,
                                tot_layer_att_align,
                                tot_max_head_att_align,
                                chain_ds,
                            )

                    if args.align_with == "instability":
                        min_residues = 10
                        if len(CA_Atoms) < min_residues:
                            log.logger.info(
                                f"Chain {code} has less than {min_residues} "
                                "valid residues... Skipping"
                            )
                            skips += 1
                        _, inst_map, contact_inst_map = \
                            process_instability.main(CA_Atoms)
                        inst_att_align = compute_attention_alignment(
                            attention, inst_map
                        )
                        contact_inst_att_align = compute_attention_alignment(
                            attention, contact_inst_map
                        )

                        chain_ds = (
                            inst_att_align,
                            contact_inst_att_align,
                        )

                        if code_idx == 0:
                            n_heads, n_layers = get_model_structure(attention)
                            tot_inst_att_align = np.zeros((n_layers, n_heads))
                            tot_contact_inst_att_align = np.zeros(
                                (n_layers, n_heads)
                            )

                        tot_inst_att_align = np.add(
                            tot_inst_att_align,
                            inst_att_align,
                        )
                        tot_contact_inst_att_align = np.add(
                            tot_contact_inst_att_align,
                            contact_inst_att_align,
                        )

                    if args.align_with == 'louvain':
                        min_residues = 10
                        if len(CA_Atoms) < min_residues:
                            log.logger.info(
                                f"Chain {code} has less than {min_residues} "
                                "valid residues... Skipping"
                            )
                            skips += 1

                        chain_amino_acids = amino_acid_df["Amino Acid"].to_list(
                        )

                        binary_contact_map, _, _, _ = align_with_contact.main(
                            attention, CA_Atoms, chain_amino_acids, att_to_aa, code,
                            save_opt='none'
                        )
                        base_graph, resolution = sum_up.prepare_complete_graph_nx(
                            CA_Atoms=CA_Atoms, binary_map=binary_contact_map)  # TODO control the indexing
                        _, _, louvain_attention_map = sum_up.get_louvain_results(
                            CA_Atoms=CA_Atoms, base_Graph=base_graph, resolution=resolution)  # can use edge_weights_combination = edge_weights
                        contact_louv_att_align = compute_attention_alignment(
                            attention, louvain_attention_map*binary_contact_map
                        )
                        louv_att_align = compute_attention_alignment(
                            attention, louvain_attention_map
                        )

                        chain_ds = (
                            louv_att_align,
                            contact_louv_att_align,
                        )

                        if code_idx == 0:
                            n_heads, n_layers = get_model_structure(attention)
                            tot_louv_att_align = np.zeros((n_layers, n_heads))
                            tot_contact_louv_att_align = np.zeros(
                                (n_layers, n_heads)
                            )

                        tot_louv_att_align = np.add(
                            tot_louv_att_align,
                            louv_att_align,
                        )
                        tot_contact_louv_att_align = np.add(
                            tot_contact_louv_att_align,
                            contact_louv_att_align,
                        )

                    if args.align_with == 'kmeans':
                        min_residues = 10
                        if len(CA_Atoms) < min_residues:
                            log.logger.info(
                                f"Chain {code} has less than {min_residues} "
                                "valid residues... Skipping"
                            )
                            skips += 1

                        chain_amino_acids = amino_acid_df["Amino Acid"].to_list(
                        )

                        binary_contact_map, _, _, _ = align_with_contact.main(
                            attention, CA_Atoms, chain_amino_acids, att_to_aa, code,
                            save_opt='none'
                        )
                        _, _, km_attention_map = sum_up.get_kmeans_results(
                            CA_Atoms=CA_Atoms)
                        contact_km_att_align = compute_attention_alignment(
                            attention, km_attention_map*binary_contact_map
                        )
                        km_att_align = compute_attention_alignment(
                            attention, km_attention_map
                        )

                        chain_ds = (
                            km_att_align,
                            contact_km_att_align,
                        )

                        if code_idx == 0:
                            n_heads, n_layers = get_model_structure(attention)
                            tot_km_att_align = np.zeros((n_layers, n_heads))
                            tot_contact_km_att_align = np.zeros(
                                (n_layers, n_heads)
                            )

                        tot_km_att_align = np.add(
                            tot_km_att_align,
                            km_att_align,
                        )
                        tot_contact_km_att_align = np.add(
                            tot_contact_km_att_align,
                            contact_km_att_align,
                        )

            sample_size = len(protein_codes) - skips

            if args.align_with == "contact":
                tot_amino_acid_df = manage_tot_ds.append_frequency_and_total(
                    tot_amino_acid_df
                )

                log.logger.info(
                    f"[bold white]GLOBAL DATA FRAME[/]\n{tot_amino_acid_df}"
                )
                tot_amino_acid_df.to_csv(
                    file_dir/"total_residue_df.csv", index=False, sep=';'
                )
                """tot_amino_acid_df and tot_att_to_aa are built by considering
                20 possible amino acids, but some of them may not be present.
                Therefore, we drop the rows relative to the amino acids with
                zero occurrences, and the tensors relative to those amino acids
                """
                tot_amino_acid_df, tot_att_to_aa = manage_tot_ds.keep_nonzero(
                    tot_amino_acid_df, tot_att_to_aa
                )

                glob_att_to_aa, glob_att_sim_df, avg_att_align = \
                    compute_on_set.main(
                        tot_amino_acid_df,
                        tot_att_head_sum,
                        tot_att_to_aa,
                        tot_head_att_align,
                        tot_layer_att_align,
                        sample_size,
                    )

                np.save(
                    file_dir/"tot_max_head_att_align.npy",
                    tot_max_head_att_align,
                )

                plotting.plot_on_set(
                    tot_amino_acid_df,
                    glob_att_to_aa,
                    glob_att_sim_df,
                    avg_att_align,
                    tot_max_head_att_align,
                )

            if args.align_with == "instability":
                avg_inst_att_align = tot_inst_att_align/len(protein_codes)
                avg_contact_inst_att_align = \
                    tot_contact_inst_att_align/len(protein_codes)

                plot_heatmap(
                    avg_inst_att_align,
                    plot_title="Average Attention-Instability Alignment"
                )
                np.save(
                    file_dir/"avg_att_align_inst.npy",
                    avg_inst_att_align,
                )
                plot_heatmap(
                    avg_contact_inst_att_align,
                    plot_title="Average Attention-Instability-Contact Alignment"
                )
                np.save(
                    file_dir/"avg_att_align_inst-contact.npy",
                    avg_contact_inst_att_align,
                )

            if args.align_with == "louvain":
                avg_louv_att_align = tot_louv_att_align/len(protein_codes)
                avg_contact_louv_att_align = \
                    tot_contact_louv_att_align/len(protein_codes)

                plot_heatmap(
                    avg_louv_att_align,
                    plot_title="Average Attention-Louvain Alignment"
                )
                np.save(
                    file_dir/"avg_att_align_louv.npy",
                    avg_louv_att_align,
                )
                plot_heatmap(
                    avg_contact_louv_att_align,
                    plot_title="Average Attention-Louvain-Contact Alignment"
                )
                np.save(
                    file_dir/"avg_att_align_louv-contact.npy",
                    avg_contact_louv_att_align,
                )

            if args.align_with == "kmeans":
                avg_km_att_align = tot_km_att_align/len(protein_codes)
                avg_contact_km_att_align = \
                    tot_contact_km_att_align/len(protein_codes)

                plot_heatmap(
                    avg_km_att_align,
                    plot_title="Average Attention-KMeans Alignment"
                )
                np.save(
                    file_dir/"avg_att_align_km.npy",
                    avg_km_att_align,
                )
                plot_heatmap(
                    avg_contact_km_att_align,
                    plot_title="Average Attention-KMeans-Contact Alignment"
                )
                np.save(
                    file_dir/"avg_att_align_km-contact.npy",
                    avg_contact_km_att_align,
                )

    if args.subparser == "on_chain":
        seq_dir = plot_dir/args.code
        seq_dir.mkdir(parents=True, exist_ok=True)

        with (
            Timer(f"Running time for [yellow]{args.code}[/yellow]"),
            torch.no_grad(),
        ):

            attention, att_head_sum, CA_Atoms, amino_acid_df, att_to_aa = \
                preprocess.main(args.code, model, tokenizer, save_opt="both")

            min_residues = 5
            if len(CA_Atoms) < min_residues:
                raise Exception(
                    f"Chain {args.code} has less than {min_residues} valid "
                    "residues... Aborting"
                )

            chain_amino_acids = amino_acid_df["Amino Acid"].to_list()

            binary_contact_map, _, _, _ = align_with_contact.main(
                attention, CA_Atoms, chain_amino_acids, att_to_aa, args.code,
                save_opt="both"
            )
            positional_aa = Collect_and_structure_data.generate_index_df(
                CA_Atoms=CA_Atoms)
            # register the layout for node and color
            layouts = {
                "node_color": args.node_color,
                "edge_color": args.edge_color,
                "edge_style": args.edge_style,
                "node_size": args.node_size
            }
            # in any case calculate the pca to get the 3 main components, to use as coords of a scatter plot
            df_for_pca = Collect_and_structure_data.get_dataframe_for_PCA(
                CA_Atoms=CA_Atoms)
            pca_df, pca_components, percentage_compatibility = PCA_computing_and_results.main(
                df_prepared_for_pca=df_for_pca)

            # select the analysis you want to conduct
            if args.analyze == "kmeans":
                kmeans_df, kmean_labels, km_attention_map = sum_up.get_kmeans_results(
                    CA_Atoms=CA_Atoms)
                color_map = {k: v for k, v in zip(
                    positional_aa, kmean_labels)}
                km_homogeneity, km_completeness, km_vmeasure = sum_up.get_partition_results(
                    CA_Atoms=CA_Atoms, df=kmeans_df)

            elif args.analyze == 'louvain':
                base_graph, resolution = sum_up.prepare_complete_graph_nx(
                    CA_Atoms=CA_Atoms, binary_map=binary_contact_map)
                edge_weights = {'contact_in_sequence': 0,
                                'lenght': 1,
                                'instability': 0}
                louvain_graph, louvain_labels, louvain_attention_map = sum_up.get_louvain_results(
                    CA_Atoms=CA_Atoms, base_Graph=base_graph, resolution=resolution)  # can use edge_weights_combination = edge_weights
                color_map = {k: v for k, v in zip(
                    positional_aa, louvain_labels)}
                louvain_homogeneity, louvain_completeness, louvain_vmeasure = sum_up.get_partition_results(
                    CA_Atoms=CA_Atoms, df=louvain_labels)

            elif args.analyze == 'only_pca':

                color_map = None  # add this option to plot 3d chain and other plotting

            # if vizualization is enabled, it has to plot graph

            # now select the kind of visualization
            if args.plot_type == 'chain3D':
                proximity_edges = Collect_and_structure_data.get_list_of_edges(CA_Atoms=CA_Atoms,
                                                                               base_map=binary_contact_map,
                                                                               type='int')
                contact_edges = [(i, i + 1) for i in range(0, len(CA_Atoms)+1)]
                netviz.plot_protein_chain_3D(CA_Atoms=CA_Atoms,
                                             edge_list1=proximity_edges,
                                             edge_list2=contact_edges,
                                             color_map=color_map,  # add option to pu color map to False in case of pca
                                             protein_name=str(args.code),
                                             save_option=False)

            elif args.plot_type == 'pca':
                netviz.plot_histogram_pca(percentage_var=percentage_compatibility,
                                          best_features=pca_components, protein_name=str(args.code), save_option=False)
                netviz.plot_pca_2d(pca_dataframe=pca_df, protein_name=str(args.code), best_features=pca_components,
                                   percentage_var=percentage_compatibility, color_map=color_map, save_option=False)
                netviz.plot_pca_3d(pca_dataframe=pca_df, protein_name=str(args.code), best_features=pca_components,
                                   percentage_var=percentage_compatibility, color_map=color_map, save_option=False)

            elif args.plot_type == 'network':
                node_opt, edge_opt, label_opt = netviz.network_layouts(network_graph=sum_up.prepare_complete_graph_nx(CA_Atoms=CA_Atoms, binary_map=binary_contact_map),
                                                                       node_layout=(
                                                                           layouts["node_color"], layouts["node_size"]),
                                                                       edge_layout=(
                                                                           layouts["edge_style"], layouts["edge_color"]),
                                                                       # add the option to put to false the color map n case of pca
                                                                       clusters_color_group=color_map,
                                                                       label=('bold', 10))
                netviz.draw_layouts(network_graph=sum_up.prepare_complete_graph_nx(CA_Atoms=CA_Atoms, binary_map=binary_contact_map),
                                    node_options=node_opt,
                                    edge_options=edge_opt,
                                    label_options=label_opt,
                                    save_option=False)

    if args.subparser == 'test_this':
        if args.testing:
            print(f'Test this {args.testing} feature')
        else:
            print('No test to run')
        code = '1DVQ'
        seq_dir = file_dir/code
        seq_dir.mkdir(parents=True, exist_ok=True)

        with (
            Timer(f"Running time for [yellow]{code}[/yellow]"),
            torch.no_grad(),
        ):

            attention, att_head_sum, CA_Atoms, amino_acid_df, att_to_aa = \
                preprocess.main(code, model, tokenizer, save_opt="plot")

            min_residues = 5
            if len(CA_Atoms) < min_residues:
                raise Exception(
                    f"Chain {code} has less than {min_residues} valid "
                    "residues... Aborting"
                )

            chain_amino_acids = amino_acid_df["Amino Acid"].to_list()

            binary_contact_map, _, _, _ = align_with_contact.main(
                attention, CA_Atoms, chain_amino_acids, att_to_aa, code,
                save_opt='none'
            )

            positional_aa = Collect_and_structure_data.generate_index_df(
                CA_Atoms=CA_Atoms)
            df_for_pca = Collect_and_structure_data.get_dataframe_for_PCA(
                CA_Atoms=CA_Atoms)
            pca_df, pca_components, percentage_compatibility = PCA_computing_and_results.main(
                df_prepared_for_pca=df_for_pca)
            color_map = None
            # netviz.plot_histogram_pca(percentage_var=percentage_compatibility,best_features=pca_components, protein_name=str(code), save_option=False)
            netviz.plot_pca_2d(pca_dataframe=pca_df, protein_name=str(code), best_features=pca_components,
                               percentage_var=percentage_compatibility, color_map=color_map, save_option=False)
            netviz.plot_pca_3d(pca_dataframe=pca_df, protein_name=str(code), best_features=pca_components,
                               percentage_var=percentage_compatibility, color_map=color_map, save_option=False)

            print(pca_df.head())
            print(
                f'the first three most compatible components are:\nPC1: {pca_components[0]} - {percentage_compatibility[0]}%\nPC2: {pca_components[1]} - {percentage_compatibility[1]}%\nPC3: {pca_components[2]} - {percentage_compatibility[2]}%')


if __name__ == '__main__':
    main()
