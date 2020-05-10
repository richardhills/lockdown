from rdhlang5.type_system.managers import get_manager

class ListInsert(object):
    def __init__(self, list):
        self.list = list

    def invoke(self, argument):
        manager = get_manager(self.list)
        manager.get_micro_op_type()
