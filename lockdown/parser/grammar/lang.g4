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
   | function // Where our language extends json...
   ;

STRING
   : '"' (ESC | SAFECODEPOINT)* '"'
   ;

SYMBOL
   : [a-zA-Z][a-zA-Z0-9]*
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
   : 'function' SYMBOL? '(' argumentDestructurings? ')' ('=>' return_type=expression)? '{' codeBlock '}'
   | 'function' SYMBOL? '(|' raw_argument=expression '|)' ('=>' return_type=expression)? '{' codeBlock '}'
   ;

argumentDestructurings
   : argumentDestructuring (',' argumentDestructuring)*
   ;

argumentDestructuring
   : expression SYMBOL
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
   | objectTemplate			# toObjectTemplate
   | listTemplate			# toListTemplate
   | expression '(' expression (',' expression)* ')' # invocation
   | expression '(|' expression '|)'     # singleParameterInvocation
   | expression '(' ')'     # noParameterInvocation
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
   | SYMBOL '=' expression  # immediateAssignment
   | expression '.' SYMBOL '=' expression  # staticAssignment
   | expression '[' expression ']' '=' expression # dynamicAssignment
   | expression '[' expression ']' '<<' expression # dynamicInsertion
   | expression '?' expression ':' expression #ternary
   | 'return' expression    # returnStatement
   | 'continue' expression  # continueStatement
   | 'break'			    # breakStatement
   | ifStatement			# toIfStatement
   | whileLoop				# toWhileLoop
   | forGeneratorLoop		# toForGeneratorLoop
   | forListLoop			# toForListLoop
   | objectType				# toObjectType
   | listType				# toListType
   | dictionaryType			# toDictionaryType
   | tupleType				# toTupleType
   | functionType			# toFunctionType
   | function				# toFunctionExpression
   ;

objectTemplate
   : '{' objectPropertyPair? (',' objectPropertyPair)* '}'
   ;

objectPropertyPair
   : SYMBOL ':' expression
   | NUMBER ':' expression
   | '[' expression ']' ':' expression
   ;

objectType
   : 'Object' '{' objectTypePropertyPair? (';' objectTypePropertyPair)* '}'
   ;

objectTypePropertyPair
   : SYMBOL ':' expression
   ;

listTemplate
   : '[' expression? (',' expression)* ']'
   ;

tupleType
   : 'Tuple' '<' expression? (',' expression)* splat? '>'
   ;

splat
   : '...'
   ;

listType
   : 'List' '<' expression '>'
   ;

dictionaryType
   : 'Dictionary' '<' expression ':' expression '>'
   ;

functionType
   : 'Function' '<' expression '=>' expression '>'
   ;

ifStatement
   : 'if' '(' expression ')' '{' codeBlock '}' ( 'else' '{' codeBlock '}' )?
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
