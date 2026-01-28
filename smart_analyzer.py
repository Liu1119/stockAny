import requests
import json
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SmartAnalyzer:
    def __init__(self, api_key=None, api_url=None):
        # 使用用户提供的DeepSeek API密钥
        self.api_key = api_key or "sk-5434f6dad2f544df9bcaf67f1d13142d"
        self.api_url = api_url or "https://api.deepseek.com/v1/chat/completions"
    
    def analyze_stock(self, stock_info):
        """
        分析单个股票
        :param stock_info: 股票信息字典
        :return: 分析结果
        """
        try:
            # 构建分析提示词
            prompt = f"请对以下股票进行分析，基于技术指标给出投资建议：\n"
            prompt += f"股票代码：{stock_info['code']}\n"
            prompt += f"股票名称：{stock_info['name']}\n"
            prompt += f"当前价格：{stock_info['price']}\n"
            prompt += f"涨跌幅：{stock_info['change']}\n"
            prompt += "技术指标：\n"
            
            for indicator, value in stock_info['indicators'].items():
                prompt += f"- {indicator}: {'是' if value else '否'}\n"
            
            prompt += "\n请给出：\n1. 短期走势判断\n2. 中期走势判断\n3. 投资建议\n4. 风险提示"
            
            # 由于是示例，我们模拟DeepSeek的分析结果
            # 在实际应用中，这里应该调用DeepSeek的API
            logger.info(f"分析股票 {stock_info['code']} - {stock_info['name']}")
            
            # 实际API调用代码
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 500
            }
            
            response = requests.post(self.api_url, headers=headers, json=data)
            response.raise_for_status()
            
            result = response.json()
            analysis_content = result['choices'][0]['message']['content']
            
            # 解析分析结果
            analysis_result = self._parse_analysis(analysis_content)
            return analysis_result
            
            # 模拟分析结果（备用）
            """
            analysis_result = {
                'short_term': '看涨',
                'medium_term': '看涨',
                'suggestion': '建议适量买入',
                'risk': '市场波动风险，注意止损'
            }
            
            return analysis_result
            """
            
        except Exception as e:
            logger.error(f"分析股票 {stock_info['code']} 失败: {str(e)}")
            # 返回默认分析结果
            return {
                'short_term': '中性',
                'medium_term': '中性',
                'suggestion': '建议观望',
                'risk': '分析失败，数据不足'
            }
    
    def _parse_analysis(self, analysis_content):
        """
        解析DeepSeek的分析结果
        :param analysis_content: 分析内容文本
        :return: 解析后的分析结果字典
        """
        # 这里需要根据DeepSeek的实际输出格式进行解析
        # 由于是示例，返回模拟结果
        return {
            'short_term': '看涨',
            'medium_term': '看涨',
            'suggestion': '建议适量买入',
            'risk': '市场波动风险，注意止损'
        }
    
    def analyze_stocks_batch(self, stocks_info):
        """
        批量分析股票
        :param stocks_info: 股票信息列表
        :return: 包含分析结果的股票信息列表
        """
        try:
            analyzed_stocks = []
            
            for stock_info in stocks_info:
                analysis_result = self.analyze_stock(stock_info)
                stock_info['analysis'] = analysis_result
                analyzed_stocks.append(stock_info)
            
            logger.info(f"批量分析完成，共分析 {len(analyzed_stocks)} 只股票")
            return analyzed_stocks
            
        except Exception as e:
            logger.error(f"批量分析股票失败: {str(e)}")
            return stocks_info