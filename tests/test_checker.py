"""
Unit tests for Axiom Type Checker & Semantic Analyzer
"""
import pytest
from axiom.lexer import Lexer
from axiom.parser import Parser
from axiom.checker import TypeChecker, SemanticError

def check_source(source: str):
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    checker = TypeChecker()
    checker.check(program)
    return checker

def test_valid_types_and_inference():
    source = """
    let a: int = 10;
    let b = 20;
    let c: float = 3.14;
    let d: bool = true;
    let s: str = "Axiom";
    let sum = a + b;
    let concat = s + " Lang";
    """
    check_source(source)

def test_int_to_float_promotion():
    source = """
    let x: float = 10; # int assigned to float is allowed
    let y = 3.14 + 10; # float + int results in float
    """
    check_source(source)

def test_undefined_variable():
    source = "let a = unknown_var + 1;"
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "Tanimlanmamis degisken: 'unknown_var'" in str(exc_info.value)

def test_undefined_variable_assignment():
    source = "z = 42;"
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "Tanimlanmamis degiskene atama: 'z'" in str(exc_info.value)

def test_immutable_variable_reassignment():
    source = """
    let x = 10;
    x = 20;
    """
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "Degistirilemez (immutable) degiskene atama yapilamaz" in str(exc_info.value)

def test_mutable_variable_reassignment():
    source = """
    let mut x = 10;
    x = 20;
    """
    check_source(source)

def test_variable_type_mismatch_on_declaration():
    source = 'let x: int = "string value";'
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "Tip uyumsuzlugu" in str(exc_info.value)

def test_variable_type_mismatch_on_assignment():
    source = """
    let mut x: int = 10;
    x = "invalid";
    """
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "Tip uyumsuzlugu" in str(exc_info.value)

def test_arithmetic_type_mismatch():
    source = 'let x = "hello" - 5;'
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "gecersizdir" in str(exc_info.value)

def test_logical_operators_require_bool():
    source = 'let x = 10 and 20;'
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "Mantiksal 'and' isleci yalnizca bool" in str(exc_info.value)

def test_unary_not_requires_bool():
    source = 'let x = not 42;'
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "'not' isleci bool bekler" in str(exc_info.value)

def test_if_condition_requires_bool():
    source = """
    if 100 {
        let a = 1;
    }
    """
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "'if' kosulu bool olmalidir" in str(exc_info.value)

def test_while_condition_requires_bool():
    source = """
    while "loop" {
        let a = 1;
    }
    """
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "'while' kosulu bool olmalidir" in str(exc_info.value)

def test_for_range_requires_integers():
    source = """
    for i in "a".."z" {
        print(i);
    }
    """
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "For araligi tam sayi" in str(exc_info.value)

def test_duplicate_function_declaration():
    source = """
    fn test_fn() {}
    fn test_fn() {}
    """
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "'test_fn' fonksiyonu zaten tanimlanmis" in str(exc_info.value)

def test_function_wrong_argument_count():
    source = """
    fn calc(a: int, b: int) -> int { return a + b; }
    calc(1);
    """
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "2 parametre bekliyor fakat 1 arguman verildi" in str(exc_info.value)

def test_function_wrong_argument_type():
    source = """
    fn calc(a: int) -> int { return a * 2; }
    calc("not an int");
    """
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "tip uyumsuzlugu: 'int' bekleniyordu, 'str' verildi" in str(exc_info.value)

def test_function_return_type_mismatch():
    source = """
    fn get_num() -> int {
        return "not a number";
    }
    """
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "Fonksiyon 'int' dondurmeli ancak 'str' donduruldu" in str(exc_info.value)

def test_function_missing_return_value():
    source = """
    fn get_num() -> int {
        return;
    }
    """
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "Fonksiyon 'int' dondurmeli ancak bos return yapildi" in str(exc_info.value)

def test_contract_requires_must_be_bool():
    source = """
    fn invalid_req(x: int)
        requires x + 10
    {
    }
    """
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "'requires' on-kosul ifadesi bool olmalidir" in str(exc_info.value)

def test_contract_ensures_must_be_bool():
    source = """
    fn invalid_ens(x: int) -> int
        ensures return * 2
    {
        return x;
    }
    """
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "'ensures' son-kosul ifadesi bool olmalidir" in str(exc_info.value)

def test_valid_contract():
    source = """
    fn valid_contract(x: int) -> int
        requires x > 0
        ensures return > x
    {
        return x + 1;
    }
    """
    check_source(source)

def test_struct_valid_declaration_and_access():
    source = """
    struct Point {
        x: int,
        y: int
    }
    let p = Point { x: 10, y: 20 };
    let px = p.x;
    let py = p.y;
    """
    check_source(source)

def test_struct_missing_field():
    source = """
    struct Point {
        x: int,
        y: int
    }
    let p = Point { x: 10 };
    """
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "alani eksik birakildi" in str(exc_info.value)

def test_struct_wrong_field_type():
    source = """
    struct Point {
        x: int,
        y: int
    }
    let p = Point { x: "wrong", y: 20 };
    """
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "Point.x" in str(exc_info.value) and "bekliyor" in str(exc_info.value)

def test_struct_nonexistent_field_access():
    source = """
    struct Point {
        x: int,
        y: int
    }
    let p = Point { x: 1, y: 2 };
    let z = p.z;
    """
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "Point' struct yapisinda 'z' alani bulunmuyor" in str(exc_info.value)

def test_array_valid_usage():
    source = """
    let arr = [10, 20, 30];
    let first = arr[0];
    let length = len(arr);
    """
    check_source(source)

def test_array_inconsistent_types():
    source = """
    let arr = [10, "string", 30];
    """
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "Dizi elemanlari ayni tipte olmalidir" in str(exc_info.value)

def test_array_non_int_index():
    source = """
    let arr = [1, 2, 3];
    let v = arr["zero"];
    """
    with pytest.raises(SemanticError) as exc_info:
        check_source(source)
    assert "Dizi indeksi 'int' olmalidir" in str(exc_info.value)

def test_len_builtin_on_string_and_array():
    source = """
    let s_len = len("axiom");
    let a_len = len([1, 2, 3, 4]);
    """
    check_source(source)

def test_network_and_time_builtins_valid():
    source = """
    let fd = tcp_connect("127.0.0.1", 8080);
    let sent = tcp_send(fd, "GET / HTTP/1.0\r\n\r\n");
    let resp = tcp_recv(fd, 1024);
    socket_close(fd);
    let now = time_now_ms();
    """
    check_source(source)
