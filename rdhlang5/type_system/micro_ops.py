from abc import abstractmethod

from rdhlang5.executor.ast_utils import compile_expression


class MicroOpType(object):
    def replace_inferred_type(self, other_micro_op_type, cache):
        raise NotImplementedError(self)

#    def apply_consistency_heuristic(self, other_micro_op_types):
#        return self

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


#     def unbind(self, source_type, key, target_manager):
#         raise NotImplementedError(self)
# 
#     def bind(self, source_type, key, target_manager):
#         raise NotImplementedError(self)

    def to_ast(self, dependency_builder, target, *args):
        args_parameters = { "arg{}".format(i): a for i, a in enumerate(args) }
        args_string = ", {" + "},{".join(args_parameters.keys()) + "}" if len(args_parameters) > 0 else ""

        return compile_expression(
            "{invoke}(get_manager({target})" + args_string + ")",
            None, dependency_builder,
            invoke=self.invoke, target=target, **args_parameters
        )

# Deprecated methods


    @abstractmethod
    def create(self, target_manager):
        raise ValueError()
        raise NotImplementedError(self)

    @abstractmethod
    def can_be_derived_from(self, type):
        raise ValueError()
        raise NotImplementedError(self)

    @abstractmethod
    def raise_on_runtime_micro_op_conflict(self, micro_op, args):
        raise ValueError()
        # Invoked on all MicroOpTypes on a class before any MicroOp is executed to check
        # for run time conflicts
        raise NotImplementedError(self)

#     def check_for_runtime_conflicts_before_adding_to_micro_op_type_to_object(self, obj, micro_op_types):
#         raise ValueError()
#         for other_micro_op_type in micro_op_types.values():
#             if not other_micro_op_type:
#                 pass
#             first_check = other_micro_op_type.check_for_new_micro_op_type_conflict(self, micro_op_types)
#             if is_debug():
#                 second_check = self.check_for_new_micro_op_type_conflict(other_micro_op_type, micro_op_types)
#                 other_micro_op_type.check_for_new_micro_op_type_conflict(self, micro_op_types)
#                 if first_check != second_check:
#                     other_micro_op_type.check_for_new_micro_op_type_conflict(self, micro_op_types)
#                     self.check_for_new_micro_op_type_conflict(other_micro_op_type, micro_op_types)
#                     raise FatalError("Type check conflict between {} and {}".format(self, other_micro_op_type))
#             if first_check:
#                 other_micro_op_type.check_for_new_micro_op_type_conflict(self, micro_op_types)
#                 raise MicroOpTypeConflict(self, other_micro_op_type)

#     @abstractmethod
#     def check_for_runtime_data_conflict(self, obj):
#         raise ValueError()
#         raise NotImplementedError(self)     

#     @abstractmethod
#     def check_for_new_micro_op_type_conflict(self, other_micro_op_type, other_micro_op_types):
#         raise ValueError()
#         raise NotImplementedError(self)


def raise_micro_op_conflicts(micro_op, args, other_micro_op_types):
    for other_micro_op_type in other_micro_op_types:
        other_micro_op_type.raise_on_runtime_micro_op_conflict(micro_op, args)


def merge_composite_types(types, name=None):
#    print "Merge {}".format([id(t) for t in types])
    from rdhlang5.type_system.composites import CompositeType

#    python_object_type_checker = None
#     for type in types:
#         if not isinstance(type, CompositeType):
#             raise FatalError()
#         if python_object_type_checker and python_object_type_checker != type.python_object_type_checker:
#             raise FatalError()
#         if type.python_object_type_checker:
#             python_object_type_checker = type.python_object_type_checker
# 
    # Optimization - remove any composite types that are empty.
    types_with_opcodes = [t for t in types if t.micro_op_types]
# 
#     # Optimization - use a global static type if safe to do so
#     if len(types_with_opcodes) == 0 and not initial_data:
#         from rdhlang5.type_system.dict_types import is_dict_checker
#         from rdhlang5.type_system.list_types import is_list_checker
#         from rdhlang5.type_system.object_types import is_object_checker
#         if python_object_type_checker == is_object_checker:
#             from rdhlang5.type_system.default_composite_types import EMPTY_OBJECT_TYPE
#             return EMPTY_OBJECT_TYPE
#         if python_object_type_checker == is_list_checker:
#             from rdhlang5.type_system.default_composite_types import EMPTY_LIST_TYPE
#             return EMPTY_LIST_TYPE
#         if python_object_type_checker == is_dict_checker:
#             from rdhlang5.type_system.default_composite_types import EMPTY_DICT_TYPE
#             return EMPTY_DICT_TYPE

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

