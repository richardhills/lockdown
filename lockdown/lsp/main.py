import json

from pygls.capabilities import COMPLETION
from pygls.lsp import CompletionItem, CompletionList, CompletionOptions, CompletionParams
from pygls.lsp.methods import HOVER, TEXT_DOCUMENT_DID_OPEN, \
    TEXT_DOCUMENT_DID_CHANGE, TEXT_DOCUMENT_DID_SAVE
from pygls.lsp.types.basic_structures import Diagnostic, Range, Position, \
    DiagnosticSeverity
from pygls.lsp.types.language_features.hover import HoverParams, Hover
from pygls.lsp.types.workspace import DidOpenTextDocumentParams, \
    DidChangeTextDocumentParams, DidSaveTextDocumentParams
from pygls.server import LanguageServer

from lockdown.executor.bootstrap import bootstrap_function, \
    get_default_global_context
from lockdown.executor.flow_control import FrameManager
from lockdown.executor.function import prepare
from lockdown.executor.opcodes import get_context_type
from lockdown.parser.parser import parse, ParseError
from lockdown.type_system.exceptions import FatalError
from lockdown.utils.utils import environment, dump_code


server = LanguageServer()


def validate(ls, params):
    with environment(base=True):
        text_doc = ls.workspace.get_document(params.text_document.uri)

        try:
            source = text_doc.source
            code = parse(source)

            outer_context = get_default_global_context()

            open_function = prepare(
                code,
                outer_context,
                FrameManager(),
                immediate_context={
                    "suggested_outer_type": get_context_type(outer_context)
                }
            )

            closed_function = open_function.close(outer_context)
            (start, end) = closed_function.get_line_and_column()

            message = str(closed_function.break_types)
            severity = DiagnosticSeverity.Warning if "exception" in closed_function.break_types else DiagnosticSeverity.Information

            ls.publish_diagnostics(text_doc.uri, [
                Diagnostic(
                    range=Range(
                        start=Position(line=start[0] - 1, character=start[1]),
                        end=Position(line=end[0] - 1, character=end[1])
                    ),
                    message=message,
                    severity=severity
                )
            ])
        except ParseError as parse_error:
            ls.publish_diagnostics(text_doc.uri, [
                Diagnostic(
                    range=Range(
                        start=Position(line=parse_error.line - 1, character=parse_error.column - 1),
                        end=Position(line=parse_error.line - 1, character=parse_error.column - 1)
                    ),
                    message=parse_error.msg,
                    severity=DiagnosticSeverity.Error
                )
            ])
        except FatalError as e:
            ls.publish_diagnostics(text_doc.uri, [
                Diagnostic(
                    range=Range(
                        start=Position(line=0, character=0),
                        end=Position(line=0, character=0)
                    ),
                    message="FatalError:{}".format(str(e.args)),
                    severity=DiagnosticSeverity.Error
                )
            ])
        except Exception as e:
            ls.publish_diagnostics(text_doc.uri, [
                Diagnostic(
                    range=Range(
                        start=Position(line=0, character=0),
                        end=Position(line=0, character=0)
                    ),
                    message=str(e),
                    severity=DiagnosticSeverity.Error
                )
            ])

@server.feature(COMPLETION, CompletionOptions(trigger_characters=['@']))
def completions(params: CompletionParams):
    """Auto completion when pressing space+ctrl"""
    return CompletionList(
        is_incomplete=False,
        items=[
            CompletionItem(label='"'),
            CompletionItem(label='['),
            CompletionItem(label=']'),
            CompletionItem(label='{'),
            CompletionItem(label='}'),
        ]
    )

# @server.feature(HOVER)
# def hover(ls, params: HoverParams):
#     """generates a hoverover effect"""
#     validate(ls, params)
#     return Hover(contents="hello world")


@server.feature(TEXT_DOCUMENT_DID_OPEN)
async def did_open(ls, params: DidOpenTextDocumentParams):
    validate(ls, params)


@server.feature(TEXT_DOCUMENT_DID_SAVE)
async def did_save(ls, params: DidSaveTextDocumentParams):
    validate(ls, params)


if __name__ == '__main__':
    server.start_io()
    # server.start_tcp('127.0.0.1', 8080)
