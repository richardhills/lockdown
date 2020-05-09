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
   : 'function' '(' expression? ')' codeBlock
   ;

codeBlock
   : '{' ( expression ';' )* '}'
   ;

expression
   : STRING					# stringExpression
   | NUMBER					# numberExpression
   | SYMBOL					# immediateDereference
   | expression '.' SYMBOL  # staticDereference
   | expression '[' expression ']' # dynamicDereference
   | '(' expression ')'     # parenthesis
   | expression '*' expression # multiplication
   | expression '/' expression # division
   | expression '+' expression # addition
   | expression '-' expression # subtraction
   | 'return' expression    # returnStatement
   | 'int'					# intTypeLiteral
   | objectType				# toObjectType
   ;

objectType
   : 'Object' '{' objectTypePropertyPair? (';' objectTypePropertyPair)* '}'
   ;

objectTypePropertyPair
   : SYMBOL ':' expression
   ;
