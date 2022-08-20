
from lockdown.type_system.core_types import Type
from lockdown.type_system.exceptions import FatalError
from lockdown.type_system.universal_type import Universal
from lockdown.utils.utils import MISSING


class Context(Universal):
    def __init__(
        self,
        static_type,
        dynamic_type,
        prepare=MISSING,
        static=MISSING,
        outer=MISSING,
        argument=MISSING,
        local=MISSING
    ):
        if not isinstance(static_type, Type):
            raise FatalError()
        if not isinstance(dynamic_type, Type):
            raise FatalError()

        initial = {
            "_types": static_type
        }
        if prepare is not MISSING:
            initial["prepare"] = prepare
        if static is not MISSING:
            initial["static"] = static
        if outer is not MISSING:
            initial["outer"] = outer
        if argument is not MISSING:
            initial["argument"] = argument
        if local is not MISSING:
            initial["local"] = local

        super(Context, self).__init__(
            True,
            initial_wrapped=initial,
            bind=dynamic_type
        )
