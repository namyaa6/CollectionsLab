from backend.eval.judge import JUDGE_PROMPT_PATH, load_judge_prompt
from backend.filehash import file_hash
from backend.prompts import PROMPTS_DIR, prompt_file_hash

# sha256 of the raw LF bytes, computed before the normalizing change.
V1_HASH = "9abc3a9de903adfac7e58cfbb2bee50768bd5b5b808961e60a2d798b88b6e500"
J1_HASH = "0ed5839d32daa8dd77ad5a8c4a1aa2483e2edf112e83ca48f840229616761566"
J1_PATH = JUDGE_PROMPT_PATH.with_name("judge_prompt_j1.yaml")


def test_existing_hashes_unchanged():
    assert prompt_file_hash("v1") == V1_HASH
    assert load_judge_prompt(J1_PATH).file_hash == J1_HASH


def test_crlf_copy_hashes_same_prompt(tmp_path):
    lf = (PROMPTS_DIR / "v1.yaml").read_bytes()
    assert b"\r" not in lf
    (tmp_path / "v1.yaml").write_bytes(lf.replace(b"\n", b"\r\n"))
    assert prompt_file_hash("v1", tmp_path) == V1_HASH


def test_crlf_copy_hashes_same_judge(tmp_path):
    lf = J1_PATH.read_bytes()
    crlf = tmp_path / "j1.yaml"
    crlf.write_bytes(lf.replace(b"\n", b"\r\n"))
    assert file_hash(crlf) == J1_HASH
    assert load_judge_prompt(crlf).file_hash == J1_HASH
