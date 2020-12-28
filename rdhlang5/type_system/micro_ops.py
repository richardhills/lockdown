from rdhlang5.executor.ast_utils import compile_expression


class MicroOpType(object):
    def invoke(self, target_manager, *args, **kwargs):
        raise NotImplementedError(self)

    def is_derivable_from(self, type):
        raise NotImplementedError(self)

    def is_bindable_to(self, target):
        raise NotImplementedError(self)

    def conflicts_with(self, our_type, other_type):
        raise NotImplementedError(self)

    def prepare_bind(self, target, key_filter):
        # Returns a tuple (nested_targets, nested_type)
        raise NotImplementedError(self)

    def merge(self, other_micro_op_type):
        raise NotImplementedError(self)

    def clone(self, **kwargs):
        raise NotImplementedError(self)

    def to_ast(self, dependency_builder, target, *args):
        args_parameters = { "arg{}".format(i): a for i, a in enumerate(args) }
        args_string = ", {" + "},{".join(args_parameters.keys()) + "}" if len(args_parameters) > 0 else ""

        return compile_expression(
            "{invoke}(get_manager({target})" + args_string + ")",
            None, dependency_builder,
            invoke=self.invoke, target=target, **args_parameters
        )

def merge_composite_types(types, name=None):
    from rdhlang5.type_system.composites import CompositeType

    types_with_opcodes = [t for t in types if t.micro_op_types]

    from rdhlang5.type_system.default_composite_types import EMPTY_COMPOSITE_TYPE

    if len(types_with_opcodes) == 0:
        return EMPTY_COMPOSITE_TYPE
    if len(types_with_opcodes) == 1:
        return CompositeType(types_with_opcodes[0].micro_op_types, name=name) 

    result = {}
    for type in types_with_opcodes:
        for tag, micro_op_type in type.micro_op_types.items():
            if tag in result:
                result[tag] = result[tag].merge(micro_op_type)
            else:
                result[tag] = micro_op_type

    return CompositeType(result, name=name)

