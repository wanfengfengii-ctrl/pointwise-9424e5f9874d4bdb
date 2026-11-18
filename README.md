# 轨道探头巡检站

值班员登记轨道探头巡检，采集员把录波器的逐槽原值和独立定位器的标记冻结成证据。源下线后，检修班凭证据签发清单。夜班按原清单号领取和导出，确认位置可用于现场复查，未知位置仍保留原读值。

## 运行

在项目根目录使用 Python 3.11。工程仅使用标准库，命令中的样例均来自 `samples/`。核验和演示在临时目录中创建库及交班件。

```sh
python3.11 -B -S -m unittest discover -s tests -p 'test_*.py'
python3.11 -B -S verify.py
python3.11 -B -S demo.py
```

`verify.py` 对整圈样例核对原槽、读值、迟到标记、离线坐标和重开后领取结果。`demo.py` 展示普通签发、整圈签发、未知位置和矛盾拒签。

## 录制与定位

录制是 UTF-8 JSON Lines。每行一个对象，事件序号按物理行从 1 开始。示例中的槽 0 读值为 8，绝对位置为 0。

```jsonl
{"kind":"reading","slot":0,"tick":0,"value":8}
{"kind":"mark","slot":0,"position":0}
{"kind":"end"}
```

读数槽从 0 起连续出现，一槽一次。圈内刻度为 0 至 9，读值和绝对位置是整数。标记可先到或晚到，同槽同值重发保留首次事件序号。同槽不同值、引用未出现的槽、空录制或没有首标均不能冻结。结束事件必须是最后一条，空白行也属于非法记录。事件对象的字段名须唯一。

位置采用绝对整数刻度，负值按模 10 取非负余数。每步位移须在 -10 至 10 之间，从第二步开始，相邻两步的有符号位移差也须在该范围内。带标槽的坐标必须等于标记。清单仅确认所有合法完整轨迹共同支持的位置。多个位置仍可解释时保留该槽原值并写出 JSON `null`，无完整轨迹时拒签。

## 库接口

```python
from contextlib import closing

from archive.issue import issue_manifest
from capture.freeze import capture_run
from handoff.evidence import get_evidence
from handoff.export import export_manifest
from handoff.lookup import get_manifest
from runs.register import open_run
from runs.store import initialize_store, open_store

with closing(open_store("station.sqlite")) as db:
    initialize_store(db)
    run = open_run(db, "ring", "morning-01", "samples/normal.jsonl")
    evidence_id = capture_run(db, run.line_id, run.run_id)
    evidence = get_evidence(db, evidence_id)
    issued = issue_manifest(db, evidence)
    original_id = issued.manifest.manifest_id
    assert get_manifest(db, original_id) == issued
    export_manifest(db, original_id, "morning-01.json")
```

首次初始化安装默认线路 `ring`。重复初始化保留已有数据和对线路显示名的编辑。巡检由线路与巡检号共同确定。同号登记同一规范路径和 SHA-256 时返回原记录，登记不同录制或未知线路时抛出 `RunError`。源文件读取和设备格式错误使用 `RecordingError`。

`capture_run` 接纳处于 `registered` 的巡检并返回固定证据号。来源改变时拒绝开始。匹配来源的回放或接纳失败会留下 `failed` 阶段，且无新包。槽和标记的接纳错误使用 `CaptureError`。固定证据和 `recorded` 阶段同次提交。证据含规范源路径、字节摘要、巡检身份、原槽号、刻度、原值、读数事件序号以及有标槽的位置和首次标记事件序号。

`get_evidence` 和 `get_manifest` 对未知号返回 `None`。签发接收已经冻结并保存的 `EvidencePack`，返回包含 `manifest` 和 `receipt` 的 `ManifestDelivery`。非法包抛出 `InvalidEvidence`，无合法轨迹抛出 `NoTrajectory`，签发存储异常抛出 `IssueWriteError`。清单、回执和交班条目一起提交，同一证据重复签发返回原成果。重开库或签发其他巡检后仍按原号读取。`fail_before_commit=True` 可在三类成果已暂存时检查回滚。

导出包含原清单号、确切证据号、线路、巡检、录制来源、原槽序和成功回执。导出成功返回目标路径，未知清单或写入失败抛出 `ExportError`。`fail_before_replace=True` 可在完成暂存后检查原交班件仍可读取。
