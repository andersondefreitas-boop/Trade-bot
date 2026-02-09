#!/usr/bin/env python3
“””
Bot do Telegram - Alertas de Trading Binance
Envia alertas em tempo real quando o setup é identificado
“””

import requests
import pandas as pd
import numpy as np
from datetime import datetime
import time
import asyncio
from typing import Dict, List

class TelegramBot:
def **init**(self, token: str, chat_id: str):
“””
Inicializa o bot do Telegram

```
    Args:
        token: Token do bot (obtido do @BotFather)
        chat_id: Seu chat ID (obtido do @userinfobot)
    """
    self.token = token
    self.chat_id = chat_id
    self.base_url = f"https://api.telegram.org/bot{token}"

def send_message(self, text: str, parse_mode: str = "HTML"):
    """Envia mensagem via Telegram"""
    try:
        url = f"{self.base_url}/sendMessage"
        data = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        response = requests.post(url, data=data)
        return response.json()
    except Exception as e:
        print(f"❌ Erro ao enviar mensagem: {e}")
        return None
```

class BinanceTelegramAlert:
def **init**(self, telegram_bot: TelegramBot, symbols: List[str], timeframe: str = ‘15m’):
“””
Sistema de alertas com Telegram

```
    Args:
        telegram_bot: Instância do TelegramBot
        symbols: Lista de pares para monitorar
        timeframe: Timeframe (15m, 1h, etc)
    """
    self.bot = telegram_bot
    self.base_url = "https://api.binance.com/api/v3"
    self.symbols = symbols
    self.timeframe = timeframe
    self.last_alerts = {}
    
def get_klines(self, symbol: str, limit: int = 500) -> pd.DataFrame:
    """Busca dados de candlesticks da Binance"""
    try:
        url = f"{self.base_url}/klines"
        params = {
            'symbol': symbol,
            'interval': self.timeframe,
            'limit': limit
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        df = pd.DataFrame(data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        return df
        
    except Exception as e:
        print(f"❌ Erro ao buscar dados de {symbol}: {e}")
        return pd.DataFrame()

def calculate_ema(self, df: pd.DataFrame, period: int) -> pd.Series:
    """Calcula EMA"""
    return df['close'].ewm(span=period, adjust=False).mean()

def calculate_vwap(self, df: pd.DataFrame) -> pd.Series:
    """Calcula VWAP"""
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    return (typical_price * df['volume']).cumsum() / df['volume'].cumsum()

def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calcula RSI"""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def check_volume_increasing(self, df: pd.DataFrame, lookback: int = 3) -> bool:
    """Verifica se volume está crescente"""
    recent_volumes = df['volume'].iloc[-lookback:].values
    if len(recent_volumes) < 2:
        return False
    return all(recent_volumes[i] < recent_volumes[i+1] for i in range(len(recent_volumes)-1))

def is_bullish_candle(self, row) -> bool:
    """Verifica se é candle de força (alta)"""
    body = abs(row['close'] - row['open'])
    total_range = row['high'] - row['low']
    
    if total_range == 0:
        return False
    
    return (row['close'] > row['open']) and (body / total_range > 0.6)

def check_buy_setup(self, symbol: str) -> Dict:
    """Verifica setup de COMPRA"""
    df = self.get_klines(symbol)
    
    if df.empty or len(df) < 200:
        return {'signal': False, 'reason': 'Dados insuficientes'}
    
    # Calcular indicadores
    df['ema_21'] = self.calculate_ema(df, 21)
    df['ema_200'] = self.calculate_ema(df, 200)
    df['vwap'] = self.calculate_vwap(df)
    df['rsi'] = self.calculate_rsi(df)
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # Verificações do setup
    checks = {
        'trend_up': last['close'] > last['ema_200'],
        'above_ema200': last['close'] > last['ema_200'],
        'near_support': (abs(last['close'] - last['ema_21']) / last['close'] < 0.015) or 
                       (abs(last['close'] - last['vwap']) / last['close'] < 0.015),
        'rsi_range': 40 <= last['rsi'] <= 65,  # Levemente flexibilizado
        'strong_candle': self.is_bullish_candle(last),
        'volume_up': self.check_volume_increasing(df, 3)
    }
    
    all_conditions = all(checks.values())
    
    result = {
        'signal': all_conditions,
        'symbol': symbol,
        'price': last['close'],
        'ema_21': last['ema_21'],
        'ema_200': last['ema_200'],
        'vwap': last['vwap'],
        'rsi': last['rsi'],
        'volume': last['volume'],
        'checks': checks,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    if all_conditions:
        result['entry'] = last['high']
        result['stop'] = min(prev['low'], last['ema_21'])
        risk = result['entry'] - result['stop']
        result['target_1'] = result['entry'] + risk
        result['target_2'] = result['entry'] + (risk * 2)
        result['target_3'] = result['entry'] + (risk * 3)
        result['risk_percent'] = (risk / result['entry']) * 100
        
    return result

def check_sell_setup(self, symbol: str) -> Dict:
    """Verifica setup de VENDA"""
    df = self.get_klines(symbol)
    
    if df.empty or len(df) < 200:
        return {'signal': False, 'reason': 'Dados insuficientes'}
    
    df['ema_21'] = self.calculate_ema(df, 21)
    df['ema_200'] = self.calculate_ema(df, 200)
    df['vwap'] = self.calculate_vwap(df)
    df['rsi'] = self.calculate_rsi(df)
    
    last = df.iloc[-1]
    
    checks = {
        'below_ema200': last['close'] < last['ema_200'],
        'vwap_above': last['vwap'] > last['close'],
        'near_resistance': (abs(last['close'] - last['ema_21']) / last['close'] < 0.015) or 
                          (abs(last['close'] - last['vwap']) / last['close'] < 0.015),
        'rejection': last['close'] < last['open'],
    }
    
    all_conditions = all(checks.values())
    
    result = {
        'signal': all_conditions,
        'symbol': symbol,
        'price': last['close'],
        'ema_21': last['ema_21'],
        'ema_200': last['ema_200'],
        'vwap': last['vwap'],
        'rsi': last['rsi'],
        'checks': checks,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    return result

def format_telegram_alert(self, setup: Dict, trade_type: str) -> str:
    """Formata alerta para Telegram (com HTML)"""
    if not setup['signal']:
        return ""
    
    emoji_type = "🟢" if trade_type == "COMPRA" else "🔴"
    
    alert = f"{emoji_type} <b>ALERTA DE {trade_type}</b> {emoji_type}\n\n"
    alert += f"💎 <b>{setup['symbol']}</b>\n"
    alert += f"⏰ {setup['timestamp']}\n"
    alert += f"━━━━━━━━━━━━━━━━━\n\n"
    
    alert += f"💰 <b>Preço:</b> ${setup['price']:.2f}\n\n"
    
    alert += f"📊 <b>Indicadores:</b>\n"
    alert += f"  • EMA 21: ${setup['ema_21']:.2f}\n"
    alert += f"  • EMA 200: ${setup['ema_200']:.2f}\n"
    alert += f"  • VWAP: ${setup['vwap']:.2f}\n"
    alert += f"  • RSI: {setup['rsi']:.1f}\n"
    
    if trade_type == "COMPRA" and 'entry' in setup:
        alert += f"\n📈 <b>Gestão de Risco:</b>\n"
        alert += f"  ➡️ Entrada: ${setup['entry']:.2f}\n"
        alert += f"  🛑 Stop: ${setup['stop']:.2f}\n"
        alert += f"  🎯 Alvo 1:1: ${setup['target_1']:.2f}\n"
        alert += f"  🎯 Alvo 1:2: ${setup['target_2']:.2f}\n"
        alert += f"  🎯 Alvo 1:3: ${setup['target_3']:.2f}\n"
        alert += f"  📊 Risco: {setup['risk_percent']:.2f}%\n"
    
    alert += f"\n✅ <b>Condições:</b>\n"
    for condition, status in setup['checks'].items():
        icon = "✓" if status else "✗"
        alert += f"  {icon} {condition.replace('_', ' ').title()}\n"
    
    # Link direto para TradingView
    tv_symbol = setup['symbol'].replace('USDT', '')
    alert += f"\n📊 <a href='https://www.tradingview.com/chart/?symbol=BINANCE:{setup['symbol']}'>Ver no TradingView</a>"
    
    return alert

def monitor(self, check_interval: int = 60):
    """Monitora continuamente e envia alertas via Telegram"""
    
    # Mensagem de início
    start_msg = f"🤖 <b>Bot Iniciado!</b>\n\n"
    start_msg += f"📊 Monitorando {len(self.symbols)} pares\n"
    start_msg += f"⏱️ Timeframe: {self.timeframe}\n"
    start_msg += f"🔄 Verificação a cada {check_interval}s\n\n"
    start_msg += f"Pares: {', '.join(self.symbols)}"
    
    self.bot.send_message(start_msg)
    print("🤖 Bot do Telegram iniciado!")
    print(f"📱 Alertas serão enviados para o chat ID: {self.bot.chat_id}\n")
    
    while True:
        try:
            for symbol in self.symbols:
                print(f"🔎 Verificando {symbol}...", end=" ")
                
                # Setup de compra
                buy_setup = self.check_buy_setup(symbol)
                if buy_setup['signal']:
                    alert_key = f"{symbol}_BUY_{datetime.now().strftime('%Y%m%d%H')}"
                    if alert_key not in self.last_alerts:
                        message = self.format_telegram_alert(buy_setup, "COMPRA")
                        self.bot.send_message(message)
                        print(f"✅ Alerta de COMPRA enviado!")
                        self.last_alerts[alert_key] = True
                
                # Setup de venda
                sell_setup = self.check_sell_setup(symbol)
                if sell_setup['signal']:
                    alert_key = f"{symbol}_SELL_{datetime.now().strftime('%Y%m%d%H')}"
                    if alert_key not in self.last_alerts:
                        message = self.format_telegram_alert(sell_setup, "VENDA")
                        self.bot.send_message(message)
                        print(f"✅ Alerta de VENDA enviado!")
                        self.last_alerts[alert_key] = True
                
                if not buy_setup['signal'] and not sell_setup['signal']:
                    print("✗ Nenhum setup")
                
                time.sleep(2)  # Evita rate limit
            
            # Limpar cache de alertas antigos
            if len(self.last_alerts) > 100:
                self.last_alerts.clear()
            
            print(f"\n⏳ Aguardando {check_interval}s...\n")
            time.sleep(check_interval)
            
        except KeyboardInterrupt:
            stop_msg = "⚠️ <b>Bot encerrado</b>\n\nMonitoramento interrompido."
            self.bot.send_message(stop_msg)
            print("\n\n⚠️ Bot encerrado pelo usuário")
            break
        except Exception as e:
            error_msg = f"❌ <b>Erro no bot:</b>\n\n<code>{str(e)}</code>"
            self.bot.send_message(error_msg)
            print(f"\n❌ Erro: {e}")
            time.sleep(30)
```

if **name** == “**main**”:
# ═══════════════════════════════════════════════════════════
# 🔧 CONFIGURAÇÃO - EDITE AQUI!
# ═══════════════════════════════════════════════════════════

```
# 1️⃣ Token do bot (obtido no @BotFather)
TELEGRAM_BOT_TOKEN = "SEU_TOKEN_AQUI"

# 2️⃣ Seu chat ID (obtido no @userinfobot)
TELEGRAM_CHAT_ID = "SEU_CHAT_ID_AQUI"

# 3️⃣ Pares para monitorar
symbols_to_monitor = [
    'BTCUSDT',
    'ETHUSDT',
    'BNBUSDT',
    'SOLUSDT',
    'ADAUSDT',
    'XRPUSDT',
    'DOGEUSDT',
    'AVAXUSDT',
]

# 4️⃣ Timeframe (15m, 1h, 4h, etc)
TIMEFRAME = '15m'

# 5️⃣ Intervalo de verificação em segundos
CHECK_INTERVAL = 60

# ═══════════════════════════════════════════════════════════

# Validação
if TELEGRAM_BOT_TOKEN == "SEU_TOKEN_AQUI" or TELEGRAM_CHAT_ID == "SEU_CHAT_ID_AQUI":
    print("❌ ERRO: Configure o token e chat ID antes de executar!")
    print("\n📖 Veja o arquivo GUIA_TELEGRAM.md para instruções")
    exit(1)

# Inicializa o bot
telegram = TelegramBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)

# Testa conexão
test_msg = telegram.send_message("🔧 <b>Teste de conexão</b>\n\nSe você recebeu esta mensagem, o bot está funcionando! ✅")

if test_msg and test_msg.get('ok'):
    print("✅ Conexão com Telegram OK!\n")
    
    # Inicia o monitoramento
    alert_system = BinanceTelegramAlert(
        telegram_bot=telegram,
        symbols=symbols_to_monitor,
        timeframe=TIMEFRAME
    )
    
    alert_system.monitor(check_interval=CHECK_INTERVAL)
else:
    print("❌ Erro ao conectar com Telegram. Verifique o token e chat ID.")
```
