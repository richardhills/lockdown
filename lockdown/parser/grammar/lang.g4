/** Taken from "The Definitive ANTLR 4 Reference" by Terence Parr */

// Derived from http://json.org
grammar lang;

json
   : value
   ;

obj
   : '{' pair (',' pair)* '}'
   | '{' '}'
   ;

pair
   : STRING ':' value
   ;

arr
   : '[' value (',' value)* ']'
   | '[' ']'
   ;

value
   : STRING
   | NUMBER
   | obj
   | arr
   | 'true'
   | 'false'
   | 'null'
   // Where our language extends json...
   | function
   | codeBlockAsFunction
   | lockdownJsonExpression
   ;

STRING
   : '"' (ESC | SAFECODEPOINT)* '"'
   ;

SYMBOL
   : [a-zA-Z_][a-zA-Z0-9_]*
   ;

fragment ESC
   : '\\' (["\\/bfnrt] | UNICODE)
   ;
fragment UNICODE
   : 'u' HEX HEX HEX HEX
   ;
fragment HEX
   : [0-9a-fA-F]
   ;
fragment SAFECODEPOINT
   : ~ ["\\\u0000-\u001F]
   ;


NUMBER
   : '-'? INT ('.' [0-9] +)? EXP?
   ;


fragment INT
   : '0' | [1-9] [0-9]*
   ;

// no leading zeros

fragment EXP
   : [Ee] [+\-]? INT
   ;

// \- since - means "range" inside [...]

WS
   : [ \t\n\r] + -> skip
   ;

function
   : dynamic='dynamic'? 'function' SYMBOL? '(' objectProperties ')' (functionBreakTypes=expression)? '{' codeBlock '}'
   | dynamic='dynamic'? 'function' SYMBOL? '(|' raw_argument=expression '|)' (functionBreakTypes=expression)? '{' codeBlock '}'
   ;

codeBlockAsFunction
   : codeBlock
   ;

lockdownJsonExpression
   : 'lockdown' '(' expression ')'
   ;

symbolInitialization
   : SYMBOL '=' expression
   ;

assignmentOrInitializationLvalue
   : SYMBOL
   | expression SYMBOL
   ;

codeBlock
   : expression symbolInitialization (',' symbolInitialization)* ';' codeBlock? # localVariableDeclaration
   | 'static' symbolInitialization ';' codeBlock? # staticValueDeclaration
   | 'typedef' expression SYMBOL ';' codeBlock? # typedef
   | function ';' codeBlock? # toFunctionStatement
   | destructuring # toDestructuring
/*   | 'import' SYMBOL ';' codeBlock? # importStatement */
   | (expression ';')+ codeBlock? # toExpression
   ;

destructuring
   : '{' assignmentOrInitializationLvalue (',' assignmentOrInitializationLvalue)* '}' '=' expression ';' codeBlock? # toObjectDestructuring
   | '[' assignmentOrInitializationLvalue (',' assignmentOrInitializationLvalue)* ']' '=' expression ';' codeBlock? # toListDestructuring
   ;

expression
   : STRING					# stringExpression
   | NUMBER					# numberExpression
   | 'true'					# trueExpression
   | 'false'				# falseExpression
   | objectTemplate			# toObjectTemplate
   | listTemplate			# toListTemplate
   | expression '(' objectProperties ')' # invocation
   | expression '<' expression (',' expression)* '>' # staticInvocation
   | expression '(|' expression '|)'     # singleParameterInvocation
   | expression '(' ')'     # noParameterInvocation
   | expression '|>' expression # pipeline
   | '(' expression ')'     # parenthesis
   | '<' expression '>'		# staticExpression
   | expression 'is' expression # is
   | SYMBOL					# immediateDereference
   | expression '.' SYMBOL  # staticDereference
   | expression '[' expression ']' unsafe='?'? # dynamicDereference
   | expression '*' expression # multiplication
   | expression '/' expression # division
   | expression '+' expression # addition
   | expression '-' expression # subtraction
   | expression '%' expression # mod
   | expression '==' expression # eq
   | expression '!=' expression # neq
   | expression '<' expression # lt
   | expression '<=' expression # lte
   | expression '>' expression # gt
   | expression '>=' expression # gte
   | expression '||' expression # boolOr
   | expression '&&' expression # boolAnd
   | expression '*|>' '{' codeBlock '}' # toMap
   | SYMBOL '=' expression  # immediateAssignment
   | expression '.' SYMBOL '=' expression  # staticAssignment
   | expression '[' expression ']' '=' expression # dynamicAssignment
   | expression '[' expression ']' '<<' expression # dynamicInsertion
   | expression '?' expression ':' expression #ternary
   | 'typeof' expression #typeof
   | 'continue' expression  # continueStatement
   | 'break'			    # breakStatement
   | ifStatement			# toIfStatement
   | loop				    # toLoop
   | whileLoop				# toWhileLoop
   | forGeneratorLoop		# toForGeneratorLoop
   | forListLoop			# toForListLoop
   | breakTypes				# toBreakTypes
   | objectType				# toObjectType
   | listType				# toListType
   | dictionaryType			# toDictionaryType
   | tupleType				# toTupleType
   | functionType			# toFunctionType
   | dynamic='dynamic'? function # toFunctionExpression
   | 'print' expression     # toPrintStatement  
   | 'return' expression    # returnStatement  
   | 'yield' expression     # yieldStatement  
   | 'export' expression    # exportStatement
   | 'json' '(' json ')'	# toJsonExpression
   ;

breakTypes
   : '=>' valueType=expression (',' breakType)*
   ;

breakType
   : SYMBOL output_type=expression ('=>' input_type=expression)?
   ; 

objectTemplate
   : '{' objectProperties '}'
   ;

objectType
   : 'Object' '{' objectProperties '}'
   ;

listTemplate
   : '[' objectProperties ']'
   ;

tupleType
   : 'Tuple' '<' expression? (',' expression)* splat2? '>'
   ;

splat2
   : '...'
   ;

listType
   : 'List' '<' expression '>'
   ;

dictionaryType
   : 'Dictionary' '<' expression ':' expression '>'
   ;

objectProperties
   : objectProperty? (',' objectProperty)* splat='...'?
   ;

objectProperty
   : splat='...'? objectKey (':' expression)?
   ;

objectKey
   : SYMBOL
   | NUMBER
   | expression
   | computed='[' expression ']'
   ;

functionType
   : 'Function' '<' expression? (',' expression)* '>' expression?
   ;

ifStatement
   : 'if' '(' expression ')' '{' codeBlock '}' ( 'else if' '(' expression ')' '{' codeBlock '}' )* ( 'else' '{' codeBlock '}' )?
   ;

loop
   : 'loop' '{' codeBlock '}'
   ;

whileLoop
   : 'while' '(' expression ')' '{' codeBlock '}'
   ;

forGeneratorLoop
   : 'for' '(var' SYMBOL 'from' expression ')' '{' codeBlock '}'
   ;

forListLoop
   : 'for' '(var' SYMBOL 'in' expression ')' '{' codeBlock '}'
   ;
