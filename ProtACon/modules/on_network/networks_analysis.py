#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__email__ = 'renatoeliasy@gmail.com'
__author__ = 'Renato Eliasy'

import numpy as np
import pandas as pd
import networkx as nx

'''
this script analyze the amminoacids in the protein, it also enhance some selected features
through colors
the dataframe used here has these basics columns:
       'AA_Name', 'AA_KD_hydrophobicity', 'AA_Volume', 'AA_Charge', 'AA_isoPH',
       'AA_Charge_Density', 'AA_Rcharge_density', 'AA_Xcoords', 'AA_Ycoords',
       'AA_Zcoords', 'AA_self_Flexibility', 'AA_HW_hydrophylicity',
       'AA_JA_in->out_E.transfer', 'AA_EM_surface.accessibility',
       'AA_local_flexibility', 'aromaticity', 'web_groups',
       'secondary_structure', 'vitality', 'AA_pos'
'''


def collect_results_about_partitions(homogeneity: float,
                                     completeness: float
                                     ) -> tuple[float, ...]:
    '''
    starting from homogeneity and completeness it returns a triplet tuple to collect
    and compute calculation about the V-measure:

    Parameters:
    ----------
    homogeneity: float
        the homogeneity score
    completeness: float
        the completeness score

    Returns:
    -------
    partitions_results : tuple[float,...]
        the V-measure, the homogeneity and the completeness
    '''
    V_measure = (homogeneity*completeness)/np.sum(homogeneity, completeness)
    V_measure = np.round(V_measure, 2)
    partitions_results = (V_measure, homogeneity, completeness)
    return partitions_results


def get_the_complete_Graph(dataframe_of_features: pd.DataFrame,
                           edges_weight_list: list[tuple[str, str, float, float, bool]] | list,
                           ) -> nx.Graph:
    """
    this function create a complete graph assigning both to the edges 
    and the nodes some attributes, depending the feature present in the dataframe_of_features and the edges_weight_list
    # FIXME add feature in the dataframe docstrings
    Parameters:
    ----------
    dataframe_of_features: pd.DataFrame
        the dataframe containing the features of the aminoacids
    edges_weight_list: list[tuple[str, str, float, float, bool]] | list
        the list of the edges with their features expressed in floats or bool

    """
    feature_to_be_in = ['AA_Name', 'AA_Coords', 'AA_Hydropathy', 'AA_Volume', 'AA_Charge', 'AA_PH', 'AA_iso_PH', 'AA_Hydrophilicity', 'AA_Surface_accessibility',
                        'AA_ja_transfer_energy_scale', 'AA_self_Flex', 'AA_local_flexibility', 'AA_secondary_structure', 'AA_aromaticity', 'AA_human_essentiality']
    for feat in feature_to_be_in:
        if not feat in dataframe_of_features.columns:
            raise ValueError(
                f'feature {feat} is not in the dataframe\nbe sure to use the correct df')
    if 'AA_pos' in dataframe_of_features.columns:
        df_x_graph = dataframe_of_features.set_index('AA_pos')
    else:
        if dataframe_of_features.index.name == 'AA_pos':
            df_x_graph = dataframe_of_features
        else:
            raise ValueError(
                'AA_pos is not in the dataframe, unable to label the nodes in the Graph')

    Completed_Graph_AAs = nx.Graph()
    for _, row in dataframe_of_features.iterrows():
        Completed_Graph_AAs.add_node(row['AA_pos'])

    node_attributes_dict = df_x_graph.to_dict(orient='index')
    nx.set_node_attributes(Completed_Graph_AAs, values=node_attributes_dict)

    for edge, distance, instability, in_contact in edges_weight_list:
        source, target = edge
        if not source in Completed_Graph_AAs.nodes:
            raise ValueError(
                f'the {source} the is not in the nodes of the Graph')
        if not target in Completed_Graph_AAs.nodes:
            raise ValueError(
                f'the {target} the is not in the nodes of the Graph')
        Completed_Graph_AAs.add_edge(
            *edge, lenght=distance, stability=-instability, contact_in_sequence=in_contact)

    return Completed_Graph_AAs


def compute_proximity_Graph(base_Graph: nx.Graph,
                            cut_off_distance: float,  # use the cut off of config.txt as default
                            feature: str = 'lenght',
                            threshold: str = 'zero' | float
                            ) -> nx.Graph:
    '''
    this function filter the edge in the complete graph: base_Graph
    to get a graph without the edge outside the threshold
    Parameters:
    ----------
    base_Graph: nx.Graph
        the complete graph to be filtered
        #FIXME add feature of edges and nodes
    cut_off_distance: float
        the distance to be used as threshold
    threshold : str
        the type of threshold to be used, it can be 'zero' or 'abs' or another floats

    Returns:
    -------
    proximity_Graph : nx.Graph
        the graph with the edges filtered in base of the threshold appllied
    '''
    proximity_Graph = base_Graph.copy()
    if isinstance(threshold, float):
        max = np.max(cut_off_distance, threshold)
        min = np.min(cut_off_distance, threshold)
        interval = range(min, max)
    if isinstance(threshold, str):
        if threshold == 'zero':
            interval = range(0, cut_off_distance)
        if threshold == 'abs':
            interval = range(-np.abs(cut_off_distance),
                             np.abs(cut_off_distance))

    # remove edges:
    for source, target in base_Graph.edges:
        if not base_Graph.get_edge_data(source, target)[feature] in interval:
            proximity_Graph.remove_edge(source, target)
    return proximity_Graph

#  create the function for louvain partitions


def weight_on_edge(contact: float = 0,
                   lenght: float = 1,
                   stability: float = 0,
                   ) -> dict:
    """
    it works with the weight on the edge, in case a linear combination on edge for modularity is required

    Parameters: 
    ----------
    contact: float
        the weight of the contact
    lenght: float
        the weight of the lenght
    stability: float
        the weight of the stability

    Returns:
    -------
    weight_dict: dict
        the dictionary containing the weights
    """
    normalized_weight = sum(contact, lenght, stability)
    weight_dict = {'contact': contact/normalized_weight, 'lenght': lenght /
                   normalized_weight, 'stability': stability/normalized_weight}
    return weight_dict


def resolution_respecting_the_kmeans(kmeans_label_dict: dict,
                                     proximity_graph: nx.Graph,
                                     ) -> int:
    """
    this function compute an approximate calculus of resolution

    Parameters:
    ----------
    kmeans_label_dict: dict
        the dictionary containing the labels of the clusters

    proximity_graph: nx.Graph
        the graph containing the edges and nodes of our interest

    Returns:
    -------
    resolution: int
        the resolution of the partition expected to be
    """
    n_clusters = 4
    n_cluster_in_graph = set([kmeans_label_dict[node]
                             for node in proximity_graph.nodes])
    resolution = len(n_cluster_in_graph)/(n_clusters)
    return resolution


def add_weight_combination(G: nx.Graph(),
                           weight_to_edge: dict
                           ) -> nx.Graph():
    '''
    it give a list of weight to use for louvain partitions

    Parameters:
    ------------
    G : networkx.Graph
        the graph to partition
    weight_to_edge : a dict containing as key the name of edge attributes, as value the weight to associate to it

    Return:
    H a networkxGraph with edge attribution weight obtained as a linear combination of input tuple

    '''
    # first check if the attributes in weight_to_edge are in list_of_attributes:
    list_of_attributes = set()
    for *_, d in G.edges(data=True):
        list_of_attributes.update(d.keys())

    for key in weight_to_edge.keys():
        if str(key) not in list_of_attributes:
            weight_to_edge[key] = 0
            raise AttributeError('the attribute {0} is not in the list of attributes of the graph'.format(
                key))  # NOTE usare qualcos'altro per risaltare l'incompatibilità: usa un logging

    for u, v, edge in G.edges(data=True):
        weight_sum = 0
        for key in weight_to_edge.keys():
            weight_sum += float(edge[key])*float(weight_to_edge[key])
        edge['weight_combination'] = weight_sum

    return G


def add_louvain_community_attribute(G: nx.Graph(),
                                    weight_of_edges: str,  # it has to be the edge attribute
                                    resolution: float  # to define granularity
                                    ) -> nx.Graph():
    '''
    adds the attribute to the nodes respecting the louvain community

    Parameters: 
    ------------
    G : nx.Graph
        the graph whose partitions has to be calculate
    weight_of_edges : str
        the attribute of the edges to consider, for modularity calculi
    resolution : float
        if resolution<1 : prefer greater communities
        if resolution>1 : prefer smaller communities

    Returns:
    --------
    H : nx.Graph
        the graph with the community attribute added to the nodes
    '''
    list_of_attributes = set()
    for *_, d in G.edges(data=True):
        list_of_attributes.update(d.keys())

    if weight_of_edges not in list_of_attributes:
        raise AttributeError(
            'the attribute {0} is not in the list of attributes of edges in this graph'.format(weight_of_edges))

    # create partitions and the dictionary to add teh corresponding attribute on each node of the graph
    partitions = nx.community.louvain_communities(
        G, weight=weight_of_edges, resolution=resolution)
    community_mapping = {}
    for community, group_of_nodes in enumerate(partitions):
        for node in group_of_nodes:
            community_mapping[node] = community

    # add the attribute:
    for node, community in community_mapping.items():
        G.nodes[node]['louvain_community'] = community

    return G
