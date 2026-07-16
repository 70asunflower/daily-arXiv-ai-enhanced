import os
import json
import sys
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
from queue import Queue
from threading import Lock
# INSERT_YOUR_CODE
import requests

import dotenv
import argparse
from tqdm import tqdm

import langchain_core.exceptions
from langchain_openai import ChatOpenAI
from langchain.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from structure import Structure
from pydantic import ValidationError

if os.path.exists('.env'):
    dotenv.load_dotenv()
template = open("template.txt", "r").read()
system = open("system.txt", "r").read()

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, required=True, help="jsonline data file")
    parser.add_argument("--max_workers", type=int, default=1, help="Maximum number of parallel workers")
    return parser.parse_args()

# 结构化输出失败时使用的默认值（必须匹配 structure.py 的 20 字段 schema）
DEFAULT_AI_FIELDS = {
    "tldr": "摘要生成失败",
    "motivation": "研究问题分析不可用",
    "method": "方法提取失败",
    "result": "结果分析不可用",
    "conclusion": "结论提取失败",
    "ai_category_tag": "",
    "sub_tags": "",
    "pillar": "Background",
    "problem": "论文摘要未明确",
    "hardware": "论文摘要未明确",
    "comm_mechanism": "论文摘要未明确",
    "memory_kv": "论文摘要未明确",
    "key_results": "论文摘要未明确",
    "baseline": "论文摘要未明确",
    "measurement": "论文摘要未明确",
    "abc_tag": "",
    "value_7xthor": "论文摘要未明确",
    "infra_assumption": "论文摘要未明确",
    "nvlink_free_holds": "论文摘要未明确",
    "differentiation": "论文摘要未明确",
    "deep_read": False,
    "deep_read_reason": "AI 处理失败",
    "open_source": "未公开",
}

def _repair_and_parse(raw: str):
    """尽力把模型返回的（可能不规范的）JSON 文本解析成 dict。"""
    if not raw:
        return None
    s = raw.strip()
    # 去掉 ```json ... ``` 代码围栏
    m = re.search(r"```(?:json)?\s*(.*?)```", s, re.DOTALL)
    if m:
        s = m.group(1).strip()
    # 截取最外层 {}
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        s = s[start:end + 1]
    # 去除尾随逗号
    s = re.sub(r",\s*([}\]])", r"\1", s)
    for cand in (s, s.replace("\n", " ").replace("\r", " ").replace("\t", " ")):
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return None

def _coerce_field(name: str, value):
    """对个别字段做类型纠正（主要是 deep_read 的 bool）。"""
    if name == "deep_read":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("true", "1", "yes", "是")
        return bool(value)
    return value

def process_single_item(chain, item: Dict, language: str) -> Dict:
    def is_sensitive(content: str) -> bool:
        """
        [DISABLED] 原先调用 spam.dw-dengwei.workers.dev 做敏感词检测。
        该端点是上游作者（dw-dengwei）的基础设施，且 fail-closed：
        一旦网络异常 / 返回非 200 / 缺字段就 return True，把整篇论文丢弃，
        会导致 enhance 步骤产出空文件、前端静默无内容（workflow 仍 exit 0）。
        同时每篇摘要都会被发往第三方端点，存在隐私与归属问题。
        现直接 return False（不触发敏感词），避免静默数据丢失。
        如需内容审核，请指向你自己的端点并替换下方实现。
        """
        return False

    def check_github_code(content: str) -> Dict:
        """提取并验证 GitHub 链接"""
        code_info = {}

        # 1. 优先匹配 github.com/owner/repo 格式
        github_pattern = r"https?://github\.com/([a-zA-Z0-9-_]+)/([a-zA-Z0-9-_\.]+)"
        match = re.search(github_pattern, content)
        
        if match:
            owner, repo = match.groups()
            # 清理 repo 名称，去掉可能的 .git 后缀或末尾的标点
            repo = repo.rstrip(".git").rstrip(".,)")
            
            full_url = f"https://github.com/{owner}/{repo}"
            code_info["code_url"] = full_url
            
            # 尝试调用 GitHub API 获取信息
            github_token = os.environ.get("TOKEN_GITHUB")
            headers = {"Accept": "application/vnd.github.v3+json"}
            if github_token:
                headers["Authorization"] = f"token {github_token}"
            
            try:
                api_url = f"https://api.github.com/repos/{owner}/{repo}"
                resp = requests.get(api_url, headers=headers, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    code_info["code_stars"] = data.get("stargazers_count", 0)
                    code_info["code_last_update"] = data.get("pushed_at", "")[:10]
            except Exception:
                # API 调用失败不影响主流程
                pass
            return code_info

        # 2. 如果没有 github.com，尝试匹配 github.io
        github_io_pattern = r"https?://[a-zA-Z0-9-_]+\.github\.io(?:/[a-zA-Z0-9-_\.]+)*"
        match_io = re.search(github_io_pattern, content)
        
        if match_io:
            url = match_io.group(0)
            # 清理末尾标点
            url = url.rstrip(".,)")
            code_info["code_url"] = url
            # github.io 不进行 star 和 update 判断
                
        return code_info

    # 检查 summary 字段
    if is_sensitive(item.get("summary", "")):
        return None

    # 检测代码可用性
    code_info = check_github_code(item.get("summary", ""))
    if code_info:
        item.update(code_info)

    """处理单个数据项 —— 调用 LLM（json_mode 结构化输出），失败时尽力修复 JSON / 重试"""
    invoke_kwargs = {
        "language": language,
        "category_tag": item.get("category_tag", "Background-支撑"),
        "pillar": item.get("pillar", "Background"),
        "matched_keywords": ", ".join(item.get("matched_keywords", [])),
        "score": f"{item.get('score', 0):.1f}",
        "content": item['summary'],
    }
    messages = prompt_template.format_prompt(**invoke_kwargs).to_messages()

    item['AI'] = dict(DEFAULT_AI_FIELDS)
    last_err = None
    for attempt in range(3):
        try:
            raw = llm.invoke(messages).content
            parsed = _repair_and_parse(raw)
            if not parsed:
                last_err = f"attempt {attempt+1}: empty/invalid JSON"
                continue
            try:
                response = Structure(**parsed)
                item['AI'] = response.model_dump()
                break
            except ValidationError as ve:
                # 部分字段可用：用默认值补齐缺失项
                merged = dict(DEFAULT_AI_FIELDS)
                for k, v in parsed.items():
                    if k in DEFAULT_AI_FIELDS:
                        merged[k] = _coerce_field(k, v)
                item['AI'] = merged
                print(f"Partial AI data for {item.get('id','unknown')}: {list(parsed.keys())}", file=sys.stderr)
                break
        except Exception as e:
            last_err = f"attempt {attempt+1}: {e}"
            continue
    else:
        print(f"All attempts failed for {item.get('id','unknown')}: {last_err}", file=sys.stderr)

    # 最终校验：所有字段存在且非空
    for field in DEFAULT_AI_FIELDS.keys():
        if field not in item['AI'] or item['AI'][field] in (None, ""):
            item['AI'][field] = DEFAULT_AI_FIELDS[field]

    # 检查 AI 生成的所有字段（敏感词）
    for v in item.get("AI", {}).values():
        if is_sensitive(str(v)):
            return None
    return item

def process_all_items(data: List[Dict], model_name: str, language: str, max_workers: int) -> List[Dict]:
    """并行处理所有数据项（json_mode 结构化输出 + 重试 + JSON 修复）"""
    llm = ChatOpenAI(
        model=model_name,
        model_kwargs={"extra_body": {"thinking": {"type": "disabled"}}},
        temperature=0,
    ).bind(response_format={"type": "json_object"})
    print('Connect to:', model_name, '(json_mode)', file=sys.stderr)

    prompt_template = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(system),
        HumanMessagePromptTemplate.from_template(template=template)
    ])

    processed_data = [None] * len(data)  # 预分配结果列表
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_idx = {
            executor.submit(process_single_item, llm, prompt_template, item, language): idx
            for idx, item in enumerate(data)
        }

        # 使用tqdm显示进度
        for future in tqdm(
            as_completed(future_to_idx),
            total=len(data),
            desc="Processing items"
        ):
            idx = future_to_idx[future]
            try:
                result = future.result()
                processed_data[idx] = result
            except Exception as e:
                print(f"Item at index {idx} generated an exception: {e}", file=sys.stderr)
                # Add default AI fields to ensure consistency
                processed_data[idx] = data[idx]
                processed_data[idx]['AI'] = dict(DEFAULT_AI_FIELDS)

    return processed_data

def main():
    args = parse_args()
    model_name = os.environ.get("MODEL_NAME", 'deepseek-chat')
    language = os.environ.get("LANGUAGE", 'Chinese')

    # 检查并删除目标文件
    target_file = args.data.replace('_top15.jsonl', '.jsonl').replace('.jsonl', f'_AI_enhanced_{language}.jsonl')
    if os.path.exists(target_file):
        os.remove(target_file)
        print(f'Removed existing file: {target_file}', file=sys.stderr)

    # 读取数据
    data = []
    with open(args.data, "r") as f:
        for line in f:
            data.append(json.loads(line))

    # 去重
    seen_ids = set()
    unique_data = []
    for item in data:
        if item['id'] not in seen_ids:
            seen_ids.add(item['id'])
            unique_data.append(item)

    data = unique_data
    print('Open:', args.data, file=sys.stderr)
    
    # 并行处理所有数据
    processed_data = process_all_items(
        data,
        model_name,
        language,
        args.max_workers
    )
    
    # 保存结果
    with open(target_file, "w") as f:
        for item in processed_data:
            if item is not None:
                f.write(json.dumps(item) + "\n")

if __name__ == "__main__":
    main()
