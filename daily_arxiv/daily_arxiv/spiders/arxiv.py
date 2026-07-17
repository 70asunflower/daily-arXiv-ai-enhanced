import scrapy
import os
import re


def _repo_root():
    """arxiv.py lives in <repo>/daily_arxiv/daily_arxiv/spiders/ -> repo root is 3 levels up."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, "..", "..", ".."))


def _load_categories_from_config():
    """Return [cat, ...] from config/research_focus.yaml (categories.core + categories.support).

    Returns None if the config is missing/unreadable or yaml is unavailable, so the
    caller can fall back to an explicit env override or a built-in default.
    """
    try:
        import yaml
    except ImportError:
        return None
    try:
        cfg_path = os.path.join(_repo_root(), "config", "research_focus.yaml")
        with open(cfg_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        cats = cfg.get("categories", {}) or {}
        merged = [str(c).strip() for c in (list(cats.get("core", [])) + list(cats.get("support", [])))]
        merged = [c for c in merged if c]
        return merged or None
    except Exception:
        return None


class ArxivSpider(scrapy.Spider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 抓取分类：config/research_focus.yaml 为单一事实来源（categories.core + categories.support）。
        # 仅当显式设置非空环境变量 CATEGORIES 时才覆盖（用于一次性 ad-hoc 调试）。
        # 这样修改研究方向时只需改 config，无需同步 GitHub Variable，
        # 杜绝“配置/变量漂移”导致静默抓错分类（此前默认 cs.CV 即此类 bug）。
        env_cats = (os.environ.get("CATEGORIES") or "").strip()
        if env_cats:
            raw = env_cats
            source = "env CATEGORIES (override)"
        else:
            cfg_cats = _load_categories_from_config()
            if cfg_cats:
                raw = ",".join(cfg_cats)
                source = "config/research_focus.yaml"
            else:
                # 配置缺失时的兜底（与 research_focus.yaml 的 core+support 一致）
                raw = "cs.DC,cs.AR,cs.PF,cs.NI,cs.OS,cs.LG,cs.ET"
                source = "built-in fallback"

        categories = [c.strip() for c in raw.split(",") if c.strip()]
        # 保存目标分类列表，用于后续验证
        self.target_categories = set(categories)
        self.logger.info("Target categories (%s): %s", source, sorted(categories))
        self.start_urls = [
            f"https://arxiv.org/list/{cat}/new" for cat in self.target_categories
        ]  # 起始URL（计算机科学领域的最新论文）

    name = "arxiv"  # 爬虫名称
    allowed_domains = ["arxiv.org"]  # 允许爬取的域名

    def parse(self, response):
        # 提取每篇论文的信息
        anchors = []
        for li in response.css("div[id=dlpage] ul li"):
            href = li.css("a::attr(href)").get()
            if href and "item" in href:
                anchors.append(int(href.split("item")[-1]))

        # 遍历每篇论文的详细信息
        for paper in response.css("dl dt"):
            paper_anchor = paper.css("a[name^='item']::attr(name)").get()
            if not paper_anchor:
                continue
                
            paper_id = int(paper_anchor.split("item")[-1])
            if anchors and paper_id >= anchors[-1]:
                continue

            # 获取论文ID
            abstract_link = paper.css("a[title='Abstract']::attr(href)").get()
            if not abstract_link:
                continue
                
            arxiv_id = abstract_link.split("/")[-1]
            
            # 获取对应的论文描述部分 (dd元素)
            paper_dd = paper.xpath("following-sibling::dd[1]")
            if not paper_dd:
                continue
            
            # 提取论文分类信息 - 在subjects部分
            subjects_text = paper_dd.css(".list-subjects .primary-subject::text").get()
            if not subjects_text:
                # 如果找不到主分类，尝试其他方式获取分类
                subjects_text = paper_dd.css(".list-subjects::text").get()
            
            if subjects_text:
                # 解析分类信息，通常格式如 "Computer Vision and Pattern Recognition (cs.CV)"
                # 提取括号中的分类代码
                categories_in_paper = re.findall(r'\(([^)]+)\)', subjects_text)
                
                # 检查论文分类是否与目标分类有交集
                paper_categories = set(categories_in_paper)
                if paper_categories.intersection(self.target_categories):
                    yield {
                        "id": arxiv_id,
                        "categories": list(paper_categories),  # 添加分类信息用于调试
                    }
                    self.logger.info(f"Found paper {arxiv_id} with categories {paper_categories}")
                else:
                    self.logger.debug(f"Skipped paper {arxiv_id} with categories {paper_categories} (not in target {self.target_categories})")
            else:
                # 如果无法获取分类信息，记录警告但仍然返回论文（保持向后兼容）
                self.logger.warning(f"Could not extract categories for paper {arxiv_id}, including anyway")
                yield {
                    "id": arxiv_id,
                    "categories": [],
                }
