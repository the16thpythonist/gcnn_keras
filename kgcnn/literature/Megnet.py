import tensorflow.keras as ks

from kgcnn.ops.models import generate_node_embedding, update_model_args, generate_edge_embedding, \
    generate_state_embedding
from kgcnn.layers.blocks import MEGnetBlock
from kgcnn.layers.keras import Dense, Add, Dropout
from kgcnn.layers.mlp import MLP
from kgcnn.layers.pooling import PoolingGlobalEdges, PoolingNodes
from kgcnn.layers.set2set import Set2Set


# from kgcnn.layers.casting import ChangeTensorType, ChangeIndexing


# Graph Networks as a Universal Machine Learning Framework for Molecules and Crystals
# by Chi Chen, Weike Ye, Yunxing Zuo, Chen Zheng, and Shyue Ping Ong*
# https://github.com/materialsvirtuallab/megnet


def make_megnet(
        # Input
        input_node_shape,
        input_edge_shape,
        input_state_shape,
        input_embedding: dict = None,
        # Output
        output_embedding: dict = None,  # Only graph possible for megnet
        output_mlp: dict = None,
        # Model specs
        meg_block_args: dict = None,
        node_ff_args: dict = None,
        edge_ff_args: dict = None,
        state_ff_args: dict = None,
        set2set_args: dict = None,
        nblocks: int = 3,
        has_ff: bool = True,
        dropout: float = None,
        use_set2set: bool = True,
):
    """Get Megnet model.

    Args:
        input_node_shape (list): Shape of node features. If shape is (None,) embedding layer is used.
        input_edge_shape (list): Shape of edge features. If shape is (None,) embedding layer is used.
        input_state_shape (list): Shape of state features. If shape is (,) embedding layer is used.
        input_embedding (dict): Dictionary of embedding parameters used if input shape is None. Default is
            {"nodes": {"input_dim": 95, "output_dim": 64},
            "edges": {"input_dim": 5, "output_dim": 64},
            "state": {"input_dim": 100, "output_dim": 64},
            'input_tensor_type': 'ragged'}.
        output_embedding (str): Dictionary of embedding parameters of the graph network. Default is
            {"output_mode": 'graph', "output_tensor_type": 'padded'}
        output_mlp (dict): Dictionary of MLP arguments for output regression or classification. Default is
            {"use_bias": [True, True, True], "units": [32, 16, 1],
            "activation": ['kgcnn>softplus2', 'kgcnn>softplus2', 'linear']}.
        meg_block_args (dict): Dictionary of MegBlock arguments. Default is
            {'node_embed': [64, 32, 32], 'edge_embed': [64, 32, 32],
            'env_embed': [64, 32, 32], 'activation': 'kgcnn>softplus2', 'is_sorted': False,
            'has_unconnected': True}.
        node_ff_args (dict): Dictionary of Feed-Forward Layer arguments. Default is
            {"units": [64, 32], "activation": "kgcnn>softplus2"}.
        edge_ff_args (dict): Dictionary of  Feed-Forward Layer arguments. Default is
            {"units": [64, 32], "activation": "kgcnn>softplus2"}.
        state_ff_args (dict): Dictionary of Feed-Forward Layer arguments. Default is
            {"units": [64, 32], "activation": "kgcnn>softplus2"}.
        set2set_args (dict): Dictionary of Set2Set Layer Arguments. Default is
            {'channels': 16, 'T': 3, "pooling_method": "sum", "init_qstar": "0"}
        nblocks (int): Number of block. Default is 3.
        has_ff (bool): Use a Feed-Forward layer. Default is True.
        dropout (float): Use dropout. Default is None.
        use_set2set (bool): Use set2set. Default is True.

    Returns:
       tf.keras.models.Model: MEGnet model.
    """
    # Default arguments if None
    model_default = {'input_embedding': {"nodes": {"input_dim": 95, "output_dim": 64},
                                         "edges": {"input_dim": 5, "output_dim": 64},
                                         "state": {"input_dim": 100, "output_dim": 64},
                                         'input_tensor_type': 'ragged'},
                     'output_embedding': {"output_mode": 'graph', "output_tensor_type": 'padded'},
                     'output_mlp': {"use_bias": [True, True, True], "units": [32, 16, 1],
                                    "activation": ['kgcnn>softplus2', 'kgcnn>softplus2', 'linear']},
                     'meg_block_args': {'node_embed': [64, 32, 32], 'edge_embed': [64, 32, 32],
                                        'env_embed': [64, 32, 32], 'activation': 'kgcnn>softplus2', 'is_sorted': False,
                                        'has_unconnected': True},
                     'set2set_args': {'channels': 16, 'T': 3, "pooling_method": "sum", "init_qstar": "0"},
                     'node_ff_args': {"units": [64, 32], "activation": "kgcnn>softplus2"},
                     'edge_ff_args': {"units": [64, 32], "activation": "kgcnn>softplus2"},
                     'state_ff_args': {"units": [64, 32], "activation": "kgcnn>softplus2"}
                     }

    # Update default arguments
    input_embedding = update_model_args(model_default['input_embedding'], input_embedding)
    output_embedding = update_model_args(model_default['output_embedding'], output_embedding)
    output_mlp = update_model_args(model_default['output_mlp'], output_mlp)
    meg_block_args = update_model_args(model_default['meg_block_args'], meg_block_args)
    set2set_args = update_model_args(model_default['set2set_args'], set2set_args)
    node_ff_args = update_model_args(model_default['node_ff_args'], node_ff_args)
    edge_ff_args = update_model_args(model_default['edge_ff_args'], edge_ff_args)
    state_ff_args = update_model_args(model_default['state_ff_args'], state_ff_args)
    state_ff_args.update({"input_tensor_type": "tensor"})

    # Make input embedding, if no feature dimension
    node_input = ks.layers.Input(shape=input_node_shape, name='node_input', dtype="float32", ragged=True)
    edge_input = ks.layers.Input(shape=input_edge_shape, name='edge_input', dtype="float32", ragged=True)
    edge_index_input = ks.layers.Input(shape=(None, 2), name='edge_index_input', dtype="int64", ragged=True)
    env_input = ks.Input(shape=input_state_shape, dtype='float32', name='state_input')
    n = generate_node_embedding(node_input, input_node_shape, input_embedding['nodes'])
    ed = generate_edge_embedding(edge_input, input_edge_shape, input_embedding['edges'])
    uenv = generate_state_embedding(env_input, input_state_shape, input_embedding['state'])
    edi = edge_index_input

    # starting
    vp = n
    ep = ed
    up = uenv
    vp = MLP(**node_ff_args)(vp)
    ep = MLP(**edge_ff_args)(ep)
    up = MLP(**state_ff_args)(up)
    vp2 = vp
    ep2 = ep
    up2 = up
    for i in range(0, nblocks):
        if has_ff and i > 0:
            vp2 = MLP(**node_ff_args)(vp)
            ep2 = MLP(**edge_ff_args)(ep)
            up2 = MLP(**state_ff_args)(up)

        # MEGnetBlock
        vp2, ep2, up2 = MEGnetBlock(**meg_block_args)(
            [vp2, ep2, edi, up2])

        # skip connection
        if dropout is not None:
            vp2 = Dropout(dropout, name='dropout_atom_%d' % i)(vp2)
            ep2 = Dropout(dropout, name='dropout_bond_%d' % i)(ep2)
            up2 = Dropout(dropout, name='dropout_state_%d' % i)(up2)

        vp = Add()([vp2, vp])
        ep = Add()([ep2, ep])
        up = Add(input_tensor_type="tensor")([up2, up])

    if use_set2set:
        vp = Dense(set2set_args["channels"], activation='linear')(vp)  # to match units
        ep = Dense(set2set_args["channels"], activation='linear')(ep)  # to match units
        vp = Set2Set(**set2set_args)(vp)
        ep = Set2Set(**set2set_args)(ep)
    else:
        vp = PoolingNodes()(vp)
        ep = PoolingGlobalEdges()(ep)

    ep = ks.layers.Flatten()(ep)
    vp = ks.layers.Flatten()(vp)
    final_vec = ks.layers.Concatenate(axis=-1)([vp, ep, up])

    if dropout is not None:
        final_vec = ks.layers.Dropout(dropout, name='dropout_final')(final_vec)

    # final dense layers
    main_output = MLP(**output_mlp, input_tensor_type="tensor")(final_vec)

    model = ks.models.Model(inputs=[node_input, edge_input, edge_index_input, env_input], outputs=main_output)

    return model
