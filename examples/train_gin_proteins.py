import tensorflow as tf
from sklearn.model_selection import train_test_split
import matplotlib.pyplot as plt
import numpy as np
import time

from kgcnn.literature.GIN import make_gin
from kgcnn.utils.data import ragged_tensor_from_nested_numpy
from kgcnn.utils.learning import LinearLearningRateScheduler

from kgcnn.data.datasets.PROTEINS import PROTEINSDatset

dataset = PROTEINSDatset()
labels, _, edge_indices, _ = dataset.get_graph()
nodes = dataset.labels_node

# Train Test split
labels_train, labels_test, nodes_train, nodes_test, edge_indices_train, edge_indices_test = train_test_split(
    labels, nodes, edge_indices,  train_size=0.9, shuffle=True)

# Convert to tf.RaggedTensor or tf.tensor
# adj_matrix copy of the data is generated by ragged_tensor_from_nested_numpy()
nodes_train, edge_indices_train = ragged_tensor_from_nested_numpy(
    nodes_train), ragged_tensor_from_nested_numpy(edge_indices_train)

nodes_test, edge_indices_test = ragged_tensor_from_nested_numpy(
    nodes_test), ragged_tensor_from_nested_numpy(edge_indices_test)

xtrain = nodes_train, edge_indices_train
xtest = nodes_test, edge_indices_test
ytrain = labels_train
ytest = labels_test

model = make_gin(
    input_node_shape=[None, 3],
    input_embedding={"nodes": {"input_dim": 800, "output_dim": 64}},
    # Output
    output_embedding={"output_mode": 'graph', "output_type": 'padded'},
    output_mlp={"use_bias": [True], "units": [2], "activation": ['linear']},
    output_activation="softmax",
    # model specs
    depth=5,
    dropout=0.5,
    gin_args={"units": [64, 64], "use_bias": True, "activation": ['relu', 'relu']}
)

# Set learning rate and epochs
batch_size = 32
learning_rate_start = 1e-2
decay_steps = 50 *batch_size
decay_rate = 0.5
epo = 350
epostep = 1

# Compile model with optimizer and loss
r_schedule = tf.keras.optimizers.schedules.ExponentialDecay(learning_rate_start,decay_steps, decay_rate, staircase=False)
optimizer = tf.keras.optimizers.Adam(learning_rate=r_schedule)
cbks = []
model.compile(loss='categorical_crossentropy',
              optimizer=optimizer,
              weighted_metrics=['categorical_accuracy'])
print(model.summary())

# Start and time training
start = time.process_time()
hist = model.fit(xtrain, ytrain,
                 epochs=epo,
                 batch_size=batch_size,
                 callbacks=cbks,
                 validation_freq=epostep,
                 validation_data=(xtest, ytest),
                 verbose=2
                 )
stop = time.process_time()
print("Print Time for taining: ", stop - start)

# Get loss from history
trainlossall = np.array(hist.history['categorical_accuracy'])
testlossall = np.array(hist.history['val_categorical_accuracy'])
acc_valid = testlossall[-1]

# Plot loss vs epochs
plt.figure()
plt.plot(np.arange(trainlossall.shape[0]), trainlossall, label='Training ACC', c='blue')
plt.plot((np.arange(len(testlossall))+1)*epostep, testlossall, label='Test ACC', c='red')
plt.scatter([trainlossall.shape[0]], [acc_valid], label="{0:0.4f} ".format(acc_valid), c='red')
plt.xlabel('Epochs')
plt.ylabel('Accuracy')
plt.title('GIN Loss')
plt.legend(loc='upper right', fontsize='x-large')
plt.savefig('gin_proteins.png')
plt.show()
