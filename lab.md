# Huong Dan Setup Lab LangGraph

File nay huong dan setup moi truong truoc khi bat dau lam project.

## 1. Co nen dung venv khong?

Nen dung `venv`.

Ly do:
- Lab dung LangGraph, LangChain provider va package LLM, cac thu vien nay thay doi version kha nhanh.
- Dung `venv` giup khong lam ban moi truong Python global.
- De xoa va cai lai neu bi loi dependency.
- Khi nop bai hoac demo, moi truong ro rang hon.

## 2. Yeu cau truoc khi setup

Can co:
- Python 3.11 tro len
- Git
- Mot API key LLM: `GEMINI_API_KEY`, `OPENAI_API_KEY`, hoac `ANTHROPIC_API_KEY`

Kiem tra Python:

```powershell
python --version
```

## 3. Tao va kich hoat venv

Chay trong thu muc project:

```powershell
python -m venv .venv
```

Kich hoat tren Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Neu PowerShell chan script, chay lenh nay roi kich hoat lai:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Khi thanh cong, terminal se co tien to `(.venv)`.

## 4. Cai dependencies

Cai tu file `requirement.txt`:

```powershell
pip install -r requirement.txt
```

Hoac cai theo package project:

```powershell
pip install -e ".[dev,google,openai,anthropic,sqlite]"
```

Neu chi dung mot provider, co the cai it hon. Vi du dung Gemini:

```powershell
pip install -e ".[dev,google]"
```

## 5. Tao file .env

Copy file mau:

```powershell
Copy-Item .env.example .env
```

Mo `.env` va dien mot API key. Vi du voi Gemini:

```env
GEMINI_API_KEY=your_key_here
```

Neu dung OpenAI:

```env
OPENAI_API_KEY=your_key_here
```

Neu dung Anthropic:

```env
ANTHROPIC_API_KEY=your_key_here
```

Co the chon model bang:

```env
LLM_MODEL=gemini-2.5-flash
```

## 6. Kiem tra setup ban dau

Chay test:

```powershell
make test
```

Neu dung Windows khong co `make`, chay truc tiep:

```powershell
pytest
```

Luu y: luc dau test co the fail vi source con nhieu `TODO(student)`. Muc tieu cua buoc nay la dam bao Python va package da cai dung.

## 7. Cac lenh hay dung khi lam lab

Chay scenario mau:

```powershell
make run-scenarios
```

Neu khong co `make`:

```powershell
python -m langgraph_agent_lab.cli run-scenarios --config configs/lab.yaml --output outputs/metrics.json
```

Neu provider LLM bi cham, bi timeout, hoac bi loi mang khi chi can sinh metrics/report local,
co the bat fallback offline:

```powershell
$env:LLM_OFFLINE_FALLBACK="true"
python -m langgraph_agent_lab.cli run-scenarios --config configs/lab.yaml --output outputs/metrics.json
```

Luu y: khi nop/cham diem that, nen tat bien nay de `classify_node` va `answer_node`
goi LLM that theo dung yeu cau lab:

```powershell
Remove-Item Env:LLM_OFFLINE_FALLBACK
```

Validate metrics:

```powershell
make grade-local
```

Neu khong co `make`:

```powershell
python -m langgraph_agent_lab.cli validate-metrics --metrics outputs/metrics.json
```

Lint code:

```powershell
ruff check src tests
```

Typecheck:

```powershell
mypy src
```

## 8. Thu tu nen lam project

Nen lam theo thu tu:

1. Doc `README.md` va `docs/LAB_GUIDE.md`
2. Hoan thien `state.py`
3. Hoan thien `routing.py`
4. Hoan thien cac node trong `nodes.py`
5. Build graph trong `graph.py`
6. Chay `pytest`
7. Chay scenarios va sinh `outputs/metrics.json`
8. Hoan thien `report.py`
9. Viet `reports/lab_report.md`
10. Neu con thoi gian, lam extension SQLite persistence hoac graph diagram

## 9. Loi thuong gap

- Chua kich hoat `.venv` nen import package bi loi.
- Chua dien API key trong `.env`.
- Cai sai provider LLM, vi du dung Gemini nhung chua cai `langchain-google-genai`.
- Graph co route khong di toi `finalize`, lam workflow khong ket thuc dung.
- Retry loop khong gioi han bang `max_attempts`.
- `classify_node` chi dung keyword heuristic, khong dung LLM structured output.

## 10. Checklist truoc khi nop

- `pytest` pass
- `outputs/metrics.json` duoc tao
- `make grade-local` pass
- `reports/lab_report.md` da dien
- `classify_node` co LLM structured output
- `answer_node` co LLM grounded generation
- Risky route co approval step
- Error route co retry va dead letter
- Khong hard-code theo scenario id hoac cau query mau
