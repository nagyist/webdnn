import os
from os import path

import argparse
import numpy as np
import chainer
import chainer.links as L
import chainer.functions as F
import chainer.computational_graph

from graph_builder.graph import operators as O
from graph_builder.graph.graph import Variable
from graph_builder.graph.operators import attributes as A
from graph_builder.graph.variables import Constant
from graph_builder.optimizer import Optimizer
from graph_builder.graph.converters.chainer import ChainerGraphConverter
from graph_builder.backend.fallback.generator import generate as generate_fallback_descriptor
from graph_builder.backend.webgpu.generator import generate as generate_webgpu_descriptor
from graph_builder.frontend.general_optimizer import GeneralOptimizer
import graph_builder.optimizer.util
from graph_builder.util.json import json

OUTPUT_DIR = path.join(path.dirname(__file__), "./output")

class MLP(chainer.Chain):

    def __init__(self, n_units, n_out):
        super(MLP, self).__init__(
            l1=L.Linear(784, n_units),  # n_in -> n_units
            l2=L.Linear(n_units, n_units),  # n_units -> n_units
            l3=L.Linear(n_units, n_out),  # n_units -> n_out
        )

    def __call__(self, x):
        h1 = F.relu(self.l1(x))
        h2 = F.relu(self.l2(h1))
        return self.l3(h2)

class CNN(chainer.Chain):
    def __init__(self, n_units, n_out):
        super(CNN, self).__init__(
            conv1=L.Convolution2D(1, n_units, 5),
            conv2=L.Convolution2D(n_units, n_units, 3, pad=1, stride=2),
            conv3=L.Convolution2D(n_units, n_out, 12)
        )

    def __call__(self, x):
        h = F.relu(self.conv1(x))#(28-5)+1=24
        h = F.relu(self.conv2(h))#floor((24+1*2-3)/2)+1=12
        h = self.conv3(h)
        return h

class CNN2(chainer.Chain):
    def __init__(self, n_units, n_out):
        super(CNN2, self).__init__(
            conv1=L.Convolution2D(1, n_units, 5),
            conv2=L.Convolution2D(n_units, n_units, 3, pad=1, stride=2),
            fc3=L.Linear(12**2*n_units, n_out)
        )

    def __call__(self, x):
        h = F.relu(self.conv1(x))#(28-5)+1=24
        h = F.relu(self.conv2(h))#floor((24+1*2-3)/2)+1=12
        h = self.fc3(h)
        return h


def main_resnet():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default="webgpu", choices=["webgpu", "fallback"])
    parser.add_argument("--optimize", action="store_true")
    args = parser.parse_args()

    link = chainer.links.model.vision.resnet.ResNet50Layers()
    dummy_input = chainer.Variable(np.random.rand(1, 3, 224, 224).astype(np.float32))#dummy image
    dummy_output = link(dummy_input, layers=['fc6'])['fc6']  # 'prob' is also possible (uses softmax)
    chainer_cg = chainer.computational_graph.build_computational_graph([dummy_output])
    converter = ChainerGraphConverter()
    graph = converter.convert(chainer_cg, [dummy_input], [dummy_output])  # type: Variable
    if args.optimize:
        graph = GeneralOptimizer().optimize(graph)

    if args.backend == "webgpu":
        descriptor, data = generate_webgpu_descriptor(graph)

    elif args.backend == "fallback":
        descriptor, data = generate_fallback_descriptor(graph)

    else:
        raise NotImplementedError()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(path.join(OUTPUT_DIR, "graph_{}.json".format(args.backend)), "w") as f:
        json.dump(descriptor, f, indent=2)

    if args.backend == "webgpu":
        with open(path.join(OUTPUT_DIR, "kernels_{}.metal".format(args.backend)), "w") as f:
            f.write(descriptor.concat_kernel_sources())

    data.tofile(path.join(OUTPUT_DIR, "weight_{}.bin".format(args.backend)))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("model")
    parser.add_argument("--unit", type=int)
    parser.add_argument("model_path")
    parser.add_argument("--backend", default="webgpu", choices=["webgpu", "fallback"])
    parser.add_argument("--optimize", action="store_true")
    args = parser.parse_args()
    if args.model == "MLP":
        link = MLP(args.unit, 10)
    elif args.model == "CNN2":
        link = CNN2(args.unit, 10)
    chainer.serializers.load_npz(args.model_path, link)

    dummy_input = chainer.Variable(np.random.rand(1, 1, 28, 28).astype(np.float32))
    dummy_output = link(dummy_input)
    chainer_cg = chainer.computational_graph.build_computational_graph([dummy_output])
    converter = ChainerGraphConverter()
    graph = converter.convert(chainer_cg, [dummy_input], [dummy_output])
    graph_builder.optimizer.util.dump(graph)

    if args.optimize:
        graph = GeneralOptimizer().optimize(graph)

    if args.backend == "webgpu":
        descriptor, data = generate_webgpu_descriptor(graph)

    elif args.backend == "fallback":
        descriptor, data = generate_fallback_descriptor(graph)

    else:
        raise NotImplementedError()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(path.join(OUTPUT_DIR, "graph_{}.json".format(args.backend)), "w") as f:
        json.dump(descriptor, f, indent=2)

    if args.backend == "webgpu":
        with open(path.join(OUTPUT_DIR, "kernels_{}.metal".format(args.backend)), "w") as f:
            f.write(descriptor.concat_kernel_sources())

    data.tofile(path.join(OUTPUT_DIR, "weight_{}.bin".format(args.backend)))

if __name__ == "__main__":
    main()
