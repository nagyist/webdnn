from typing import Type

import numpy as np

from graph_builder.graph.attribute import Attribute
from graph_builder.graph.graph import Variable
from graph_builder.graph.variables import attributes as VA


class Constant(Variable):
    data: np.array

    def __init__(self, data: np.array, order: Type[Attribute]):
        super(Constant, self).__init__(data.shape, order)
        self.data = data
        self.attributes.add(VA.Constant)

    def __repr__(self):
        order_repr = ''.join(map(lambda e: e.name, self.axis_order.axes))
        return f"<Constant shape={self.shape}, order=\"{order_repr}\">"

    def change_axis_order(self, axis_order: Type[Attribute]):
        assert issubclass(axis_order, VA.AxisOrder)
        # 次元数を減らす時は、なくなる次元のサイズが1のときだけOK
        # 増える次元は、サイズ1
        current_shape_dict = self.shape_dict
        new_shape = [current_shape_dict.get(axis, 1) for axis in axis_order.axes]
        for axis, size in current_shape_dict.items():
            if axis not in axis_order.axes:
                assert size == 1

        if len(self.axis_order.axes) == len(axis_order.axes):
            #  新しい軸がもとの軸で何番目かを列挙
            trans_axes = tuple(current_shape_dict[axis] for axis in axis_order.axes)
            self.data = np.transpose(self.data, trans_axes)
        else:
            #  別に実装できないわけではないが手抜き
            raise NotImplementedError()

        self.axis_order = axis_order
        self.shape = new_shape
