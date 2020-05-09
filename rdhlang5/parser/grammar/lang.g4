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
   | function
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
   : 'function' '(' expression? ')' '{' codeBlock '}'
   ;

symbolInitialization
   : SYMBOL '=' expression
   ;

codeBlock
   : expression symbolInitialization (',' symbolInitialization)* ';' codeBlock? # localVariableDeclaration
   | 'static' symbolInitialization ';' codeBlock? # staticValueDeclaration
   | 'typedef' expression SYMBOL ';' codeBlock? # typedef
/*   | 'import' SYMBOL ';' codeBlock? # importStatement */
   | (expression ';')+ codeBlock? # toExpression
   ;

expression
   : STRING					# stringExpression
   | NUMBER					# numberExpression
   | objectTemplate			# toObjectTemplate
   | listTemplate			# toListTemplate
   | '(' expression ')'     # parenthesis
   | SYMBOL					# immediateDereference
   | expression '.' SYMBOL  # staticDereference
   | expression '[' expression ']' # dynamicDereference
   | expression '*' expression # multiplication
   | expression '/' expression # division
   | expression '+' expression # addition
   | expression '-' expression # subtraction
   | SYMBOL '=' expression  # immediateAssignment
   | expression '.' SYMBOL '=' expression  # staticAssignment
   | expression '[' expression ']' '=' expression # dynamicAssignment
   | 'return' expression    # returnStatement
   | 'int'					# intTypeLiteral
   | objectType				# toObjectType
   | listType				# toListType
   ;

objectTemplate
   : '{' objectPropertyPair? (';' objectPropertyPair)* '}'
   ;

objectPropertyPair
   : SYMBOL ':' expression
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

listType
   : 'List' '<' expression '>'
   ;
