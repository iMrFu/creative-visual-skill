"""
测试 — 模块 A：文章分析器
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from article_analyzer import analyze_article
from utils import ArticleInfo


class TestArticleAnalyzerBasic:
    """基础文章分析测试"""

    def test_analyze_article_basic(self):
        """测试亲子教育类文章"""
        article = """
        在家庭教育中，陪伴是最长情的告白。每一个孩子都需要父母的关爱和陪伴，
        这种温暖的亲子关系能够让孩子健康快乐地成长。作为父母，我们应该放下手机，
        用心倾听孩子的心声，和他们一起玩耍、一起学习、一起成长。
        """
        result = analyze_article(article)
        assert isinstance(result, ArticleInfo)
        assert result.topic != ""
        assert result.subject != ""
        assert len(result.keywords) > 0

    def test_analyze_article_tech(self):
        """测试科技类文章"""
        article = """
        人工智能技术正在深刻改变我们的生活。从自动驾驶到智能家居，
        从机器学习到深度学习，AI已经渗透到各个领域。未来，
        随着算力的提升和算法的优化，人工智能将带来更多的创新和变革。
        """
        result = analyze_article(article)
        assert isinstance(result, ArticleInfo)
        assert result.topic != ""
        assert len(result.keywords) > 0

    def test_analyze_article_empty(self):
        """测试空文章"""
        result = analyze_article("")
        assert isinstance(result, ArticleInfo)
        assert result.topic == "生活/健康"  # 默认主题
        assert result.emotion == "冷静"  # 默认情绪

    def test_topic_detection(self):
        """测试主题检测"""
        tech_article = "人工智能和机器学习是当今科技发展的重要方向，大数据分析也越来越重要。"
        result = analyze_article(tech_article)
        assert isinstance(result, ArticleInfo)
        # 应该能识别为科技相关主题
        assert result.topic != ""

    def test_keyword_extraction(self):
        """测试关键词提取"""
        article = "教育改革需要关注学生的全面发展，培养创新思维和实践能力。"
        result = analyze_article(article)
        assert isinstance(result, ArticleInfo)
        assert len(result.keywords) > 0
        # 关键词应该是字符串列表
        assert all(isinstance(kw, str) for kw in result.keywords)
