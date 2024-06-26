import json
import glob
import os
import pytest
import resource
import subprocess
import sys

# Set a memory limit of 4GB
resource.setrlimit(resource.RLIMIT_AS, (4 * 1024 * 1024 * 1024, -1))

testcase_dir = './test/'

@pytest.mark.parametrize('wasm_path, entry', [
    ('hello_world.wasm', ''),
    ('hello_world_go.wasm', '_start'),
    ('hello_world_rust.wasm', ''),
    ('test.wasm', ''),
    ('password.wasm', '')
])

def test_wasm_can_be_analyzed(wasm_path, entry):
    wasm_path = os.path.join(testcase_dir, wasm_path)
    cmd = [sys.executable, 'launcher.py', '-f', wasm_path, '-s', '-v', 'info']
    if entry != "":
        cmd.extend(['--entry', entry])
    subprocess.run(cmd, timeout=900, check=True)

def test_return_simulation():
    wasm_path = './test/test_return.wasm'
    cmd = [sys.executable, 'launcher.py', '-f', wasm_path, '-s', '-v', 'info', '--source_type', 'rust']
    subprocess.run(cmd, timeout=900, check=True)

    result_dir = glob.glob('./log/result/test_return_*')
    assert len(result_dir) == 1, 'more than one matching results, do you have multiple `test_return*` cases?'
    result_dir = result_dir[0]
    state_path = glob.glob(f'{result_dir}/state*.json')
    assert len(state_path) == 1, 'should have only one state output `Exit 0`'

    with open(state_path[0], 'r') as f:
        state = json.load(f)
    assert state['Solution']['proc_exit'] == "\u0000", f'exit code should be 0, got {state["Solution"]["proc_exit"]}'

def test_unreachable_simulation():
    wasm_path = './test/test_unreachable.wasm'
    cmd = [sys.executable, 'launcher.py', '-f', wasm_path, '-s', '-v', 'info', '--source_type', 'rust']
    subprocess.run(cmd, timeout=900, check=True)

    result_dir = glob.glob('./log/result/test_unreachable_*')
    assert len(result_dir) == 1, 'more than one matching results, do you have multiple `test_unreachable*` cases?'
    result_dir = result_dir[0]
    state_path = glob.glob(f'{result_dir}/state*.json')
    assert len(state_path) == 1, 'should have only one state output `null`'
    with open(state_path[0], 'r') as f:
        state = json.load(f)
    assert state['Solution'] == {}, f'should have no solution, got {state["Solution"]}'

def test_hello_c_to_wasm():
    source_path = "./test/c/src/hello.c"
    cmd = ["clang", "-g", source_path, "-o", "hello_c.wasm"]
    subprocess.run(cmd, timeout=10, check=True)
    assert os.path.exists("hello_c.wasm"), "hello_c.wasm not found. Compilation failed."
    cmd = [sys.executable, 'launcher.py', '-f', "hello_c.wasm", '-s', '-v', 'info', '--source_type', 'c', '--entry', '__main_void']
    subprocess.run(cmd, timeout=10, check=True)
    os.remove("hello_c.wasm")
    os.remove("hello_c.wat")

    result_dir = glob.glob('./log/result/hello_c*')
    assert len(result_dir) == 1, 'more than one matching results, do you have multiple `hello_c*` cases?'
    result_dir = result_dir[0]
    state_path = glob.glob(f'{result_dir}/state*.json')
    assert len(state_path) == 1, 'should have only one state output'
    with open(state_path[0], 'r') as f:
        state = json.load(f)
    assert state['Output'][0] == {
        "name": "stdout",
        "output": "Hello, world!\n"
    }, f'output mismatched, got {state["Output"]}'

def test_hello_rust_to_wasm():
    source_dir = "./test/rust/hello"
    expected_wasm_path = "./test/rust/hello/target/wasm32-wasi/debug/hello_rust.wasm"
    cmd = ["cargo", "build", "--target", "wasm32-wasi"]
    subprocess.run(cmd, cwd=source_dir, timeout=10, check=True)
    assert os.path.exists(expected_wasm_path), "hello_rust.wasm not found. Compilation failed."
    cmd = [sys.executable, 'launcher.py', '-f', expected_wasm_path, '-s', '-v', 'info', '--source_type', 'rust', '--entry', '__main_void']
    subprocess.run(cmd, timeout=10, check=True)
    cmd = ["rm", "-rf", "./test/rust/hello/target"]
    subprocess.run(cmd, timeout=10, check=True)

    result_dir = glob.glob('./log/result/hello_rust*')
    assert len(result_dir) == 1, 'more than one matching results, do you have multiple `hello_rust*` cases?'
    result_dir = result_dir[0]
    state_path = glob.glob(f'{result_dir}/state*.json')
    assert len(state_path) == 1, 'should have only one state output'
    with open(state_path[0], 'r') as f:
        state = json.load(f)
    assert state['Output'][0] == {
        "name": "stdout",
        "output": "Hello, world!\n"
    }, f'output mismatched, got {state["Output"]}'