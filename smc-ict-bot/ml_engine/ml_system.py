"""
═══════════════════════════════════════════════════════════════════
🧠 Machine Learning Engine for Trading
═══════════════════════════════════════════════════════════════════
نظام ML يتعلم من الأخطاء ويحسّن Confluence Score

المكونات:
1. Feature Engineering - استخراج الميزات
2. Model Training - تدريب النماذج
3. Online Learning - تعلم مستمر
4. Performance Tracking - تتبع الأداء
5. Auto-Improvement - تحسين تلقائي

المكتبات:
- scikit-learn (ML الأساسي)
- XGBoost (Gradient Boosting)
- TensorFlow/PyTorch (Deep Learning)
- Optuna (Hyperparameter Tuning)
═══════════════════════════════════════════════════════════════════
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
import pickle
import os
from loguru import logger

# ML Libraries
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import xgboost as xgb


@dataclass
class TradeResult:
    """نتيجة صفقة للتعلم منها"""
    trade_id: str
    symbol: str
    timestamp: datetime

    # Features used for decision
    features: Dict

    # Prediction
    predicted_score: float
    predicted_confidence: float

    # Actual result
    actual_pnl: float
    actual_pnl_pct: float
    was_winner: bool

    # Market context
    htf_trend: str
    pattern_type: str
    confluence_components: Dict


@dataclass
class ModelMetrics:
    """مقاييس أداء النموذج"""
    timestamp: datetime
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    total_samples: int
    win_rate_predicted: float
    win_rate_actual: float


class FeatureEngineer:
    """استخراج الميزات من بيانات السوق"""

    def __init__(self):
        self.feature_names = [
            # Technical features
            'rsi', 'macd', 'atr', 'volume_ratio',
            # SMC features
            'liquidity_sweep_strength', 'ob_strength', 'fvg_size_atr',
            # Structure features
            'htf_trend_numeric', 'ltf_choch_present', 'bos_present',
            # Time features
            'hour_utc', 'day_of_week', 'is_kill_zone',
            # Price action
            'candle_body_ratio', 'upper_wick_ratio', 'lower_wick_ratio',
            # Volume
            'volume_spike', 'volume_trend',
            # Premium/Discount
            'price_position', 'distance_to_equilibrium',
            # Confluence
            'confluence_count', 'nearest_ob_distance', 'nearest_fvg_distance',
        ]

    def extract_features(
        self,
        df: pd.DataFrame,
        smc_analysis: Dict,
        market_context: Dict,
    ) -> np.ndarray:
        """استخراج كل الميزات من البيانات"""
        features = {}

        # Technical indicators
        features['rsi'] = self._calculate_rsi(df).iloc[-1]
        features['macd'] = self._calculate_macd(df).iloc[-1]
        features['atr'] = self._calculate_atr(df).iloc[-1]

        avg_vol = df['volume'].rolling(20).mean().iloc[-1]
        features['volume_ratio'] = df['volume'].iloc[-1] / avg_vol if avg_vol > 0 else 1

        # SMC features
        features['liquidity_sweep_strength'] = smc_analysis.get('sweep_strength', 0)
        features['ob_strength'] = smc_analysis.get('ob_strength', 0)
        features['fvg_size_atr'] = smc_analysis.get('fvg_size', 0)

        # Structure
        trend_map = {'bullish': 1, 'bearish': -1, 'ranging': 0}
        features['htf_trend_numeric'] = trend_map.get(smc_analysis.get('htf_trend', 'ranging'), 0)
        features['ltf_choch_present'] = 1 if smc_analysis.get('choch') else 0
        features['bos_present'] = 1 if smc_analysis.get('bos') else 0

        # Time
        now = datetime.now()
        features['hour_utc'] = now.hour
        features['day_of_week'] = now.weekday()
        features['is_kill_zone'] = 1 if 2 <= now.hour <= 12 else 0

        # Price action
        last_candle = df.iloc[-1]
        total_range = last_candle['high'] - last_candle['low']
        if total_range > 0:
            body = abs(last_candle['close'] - last_candle['open'])
            features['candle_body_ratio'] = body / total_range
            features['upper_wick_ratio'] = (last_candle['high'] - max(last_candle['open'], last_candle['close'])) / total_range
            features['lower_wick_ratio'] = (min(last_candle['open'], last_candle['close']) - last_candle['low']) / total_range
        else:
            features['candle_body_ratio'] = 0
            features['upper_wick_ratio'] = 0
            features['lower_wick_ratio'] = 0

        # Volume
        features['volume_spike'] = 1 if features['volume_ratio'] > 1.5 else 0
        vol_5 = df['volume'].tail(5).mean()
        vol_20 = df['volume'].tail(20).mean()
        features['volume_trend'] = vol_5 / vol_20 if vol_20 > 0 else 1

        # Premium/Discount
        high_50 = df['high'].tail(50).max()
        low_50 = df['low'].tail(50).min()
        if high_50 > low_50:
            range_50 = high_50 - low_50
            current = last_candle['close']
            features['price_position'] = (current - low_50) / range_50
            features['distance_to_equilibrium'] = abs(current - (low_50 + range_50/2)) / range_50
        else:
            features['price_position'] = 0.5
            features['distance_to_equilibrium'] = 0

        # Confluence
        features['confluence_count'] = smc_analysis.get('confluence_count', 0)
        features['nearest_ob_distance'] = smc_analysis.get('nearest_ob_distance', 999)
        features['nearest_fvg_distance'] = smc_analysis.get('nearest_fvg_distance', 999)

        # تحويل لـ numpy array
        return np.array([features.get(name, 0) for name in self.feature_names])

    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def _calculate_macd(self, df: pd.DataFrame) -> pd.Series:
        ema_12 = df['close'].ewm(span=12).mean()
        ema_26 = df['close'].ewm(span=26).mean()
        return ema_12 - ema_26

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        tr = pd.concat([
            df['high'] - df['low'],
            abs(df['high'] - df['close'].shift()),
            abs(df['low'] - df['close'].shift())
        ], axis=1).max(axis=1)
        return tr.rolling(period).mean()


class TradingMLModel:
    """
    نموذج ML للتداول
    يتعلم من الصفقات السابقة ويتحسن باستمرار
    """

    def __init__(self, model_dir: str = "ml_engine/models"):
        self.model_dir = model_dir
        os.makedirs(model_dir, exist_ok=True)

        # النموذج الرئيسي (XGBoost - الأسرع والأقوى)
        self.model = xgb.XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            objective='binary:logistic',
            random_state=42,
            n_jobs=-1,
        )

        # Scaler لتطبيع البيانات
        self.scaler = StandardScaler()

        # البيانات
        self.feature_engineer = FeatureEngineer()
        self.training_data: List[TradeResult] = []
        self.metrics_history: List[ModelMetrics] = []

        # الإحصائيات
        self.total_predictions = 0
        self.correct_predictions = 0
        self.last_retrain = None

        # Try to load existing model
        self._load_model()

        logger.info("🧠 ML Model initialized")

    def predict(
        self,
        df: pd.DataFrame,
        smc_analysis: Dict,
        market_context: Dict = None,
    ) -> Tuple[float, float]:
        """
        تنبؤ بجودة الـ Setup

        Returns:
            (success_probability, confidence)
        """
        try:
            # استخراج الميزات
            features = self.feature_engineer.extract_features(
                df, smc_analysis, market_context or {}
            )

            # تطبيع
            features_scaled = self.scaler.transform(features.reshape(1, -1))

            # تنبؤ الاحتمالية
            prob = self.model.predict_proba(features_scaled)[0]

            success_prob = prob[1]  # احتمالية النجاح
            confidence = max(prob)   # الثقة في التنبؤ

            self.total_predictions += 1

            return success_prob, confidence

        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return 0.5, 0.0

    def learn_from_trade(self, result: TradeResult):
        """
        التعلم من نتيجة صفقة
        يُحدّث النموذج ببطء (Online Learning)
        """
        try:
            # إضافة للبيانات
            self.training_data.append(result)

            # تحديث الإحصائيات
            if result.was_winner:
                self.correct_predictions += 1

            # إعادة تدريب كل 50 صفقة
            if len(self.training_data) >= 50 and len(self.training_data) % 50 == 0:
                logger.info(f"🔄 Retraining model with {len(self.training_data)} samples...")
                self.retrain()

            # حفظ البيانات
            self._save_training_data()

        except Exception as e:
            logger.error(f"Learning failed: {e}")

    def retrain(self):
        """إعادة تدريب النموذج على كل البيانات"""
        try:
            if len(self.training_data) < 20:
                logger.warning("Not enough data to retrain")
                return

            # تحضير البيانات
            X, y = self._prepare_training_data()

            if len(X) < 10:
                return

            # Train/Test Split
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )

            # تطبيع
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)

            # تدريب
            self.model.fit(X_train_scaled, y_train)

            # تقييم
            y_pred = self.model.predict(X_test_scaled)

            metrics = ModelMetrics(
                timestamp=datetime.now(),
                accuracy=accuracy_score(y_test, y_pred),
                precision=precision_score(y_test, y_pred, zero_division=0),
                recall=recall_score(y_test, y_pred, zero_division=0),
                f1_score=f1_score(y_test, y_pred, zero_division=0),
                total_samples=len(self.training_data),
                win_rate_predicted=self.model.predict_proba(X_test_scaled)[:, 1].mean(),
                win_rate_actual=y_test.mean(),
            )

            self.metrics_history.append(metrics)
            self.last_retrain = datetime.now()

            # حفظ
            self._save_model()

            logger.success(
                f"✅ Model retrained: "
                f"Accuracy={metrics.accuracy:.2%}, "
                f"Precision={metrics.precision:.2%}, "
                f"F1={metrics.f1_score:.2%}"
            )

            # Feature Importance
            self._log_feature_importance()

        except Exception as e:
            logger.error(f"Retrain failed: {e}")

    def _prepare_training_data(self) -> Tuple[np.ndarray, np.ndarray]:
        """تحضير بيانات التدريب"""
        X = []
        y = []

        for result in self.training_data:
            features = self.feature_engineer.extract_features(
                pd.DataFrame(),  # في الإنتاج، نحتاج بيانات حقيقية
                result.features,
                {}
            )
            X.append(features)
            y.append(1 if result.was_winner else 0)

        return np.array(X), np.array(y)

    def _log_feature_importance(self):
        """عرض أهمية الميزات"""
        try:
            importance = self.model.feature_importances_
            feature_importance = sorted(
                zip(self.feature_engineer.feature_names, importance),
                key=lambda x: x[1],
                reverse=True
            )

            logger.info("📊 Top 5 Important Features:")
            for name, imp in feature_importance[:5]:
                logger.info(f"   {name}: {imp:.3f}")

        except Exception as e:
            logger.error(f"Feature importance failed: {e}")

    def get_improved_confluence_score(
        self,
        base_score: int,
        df: pd.DataFrame,
        smc_analysis: Dict,
    ) -> int:
        """
        تحسين Confluence Score باستخدام ML
        يدمج الـ Score التقليدي مع تنبؤات ML
        """
        try:
            # تنبؤ ML
            ml_prob, ml_confidence = self.predict(df, smc_analysis)

            # Score التقليدي (0-100)
            # Score ML (0-100)
            ml_score = int(ml_prob * 100)

            # دمج ذكي: إذا ML واثق، اعطيه وزن أكبر
            if ml_confidence > 0.7:
                # ML ثقته عالية = وزنه أكبر
                final_score = (base_score * 0.4) + (ml_score * 0.6)
            else:
                # ثقة منخفضة = الـ score التقليدي هو الأساس
                final_score = (base_score * 0.7) + (ml_score * 0.3)

            return int(final_score)

        except Exception as e:
            logger.error(f"ML scoring failed: {e}")
            return base_score

    def get_performance_report(self) -> Dict:
        """تقرير أداء النموذج"""
        if not self.metrics_history:
            return {'status': 'No metrics yet'}

        latest = self.metrics_history[-1]

        return {
            'accuracy': latest.accuracy,
            'precision': latest.precision,
            'recall': latest.recall,
            'f1_score': latest.f1_score,
            'total_samples': latest.total_samples,
            'total_predictions': self.total_predictions,
            'correct_predictions': self.correct_predictions,
            'prediction_accuracy': (
                self.correct_predictions / self.total_predictions
                if self.total_predictions > 0 else 0
            ),
            'last_retrain': self.last_retrain.isoformat() if self.last_retrain else None,
            'model_status': 'trained' if self.last_retrain else 'untrained',
        }

    def _save_model(self):
        """حفظ النموذج"""
        try:
            model_path = os.path.join(self.model_dir, 'xgboost_model.pkl')
            scaler_path = os.path.join(self.model_dir, 'scaler.pkl')

            with open(model_path, 'wb') as f:
                pickle.dump(self.model, f)

            with open(scaler_path, 'wb') as f:
                pickle.dump(self.scaler, f)

        except Exception as e:
            logger.error(f"Save model failed: {e}")

    def _load_model(self):
        """تحميل النموذج"""
        try:
            model_path = os.path.join(self.model_dir, 'xgboost_model.pkl')
            scaler_path = os.path.join(self.model_dir, 'scaler.pkl')

            if os.path.exists(model_path) and os.path.exists(scaler_path):
                with open(model_path, 'rb') as f:
                    self.model = pickle.load(f)

                with open(scaler_path, 'rb') as f:
                    self.scaler = pickle.load(f)

                logger.success("✅ Model loaded from disk")
                self.last_retrain = datetime.now()

        except Exception as e:
            logger.warning(f"Load model failed: {e}")

    def _save_training_data(self):
        """حفظ بيانات التدريب"""
        try:
            data_path = os.path.join(self.model_dir, 'training_data.pkl')
            with open(data_path, 'wb') as f:
                pickle.dump(self.training_data, f)
        except Exception as e:
            logger.error(f"Save data failed: {e}")


# ════════════════════════════════════════════════════════════════
# 🔄 نظام التعلم المستمر (Continuous Learning Loop)
# ════════════════════════════════════════════════════════════════


class ContinuousLearningSystem:
    """
    نظام التعلم المستمر الذي يحلل الأخطاء ويتحسن
    """

    def __init__(self, ml_model: TradingMLModel):
        self.ml_model = ml_model
        self.error_patterns: Dict = {}
        self.improvement_log: List[Dict] = []

        logger.info("🔄 Continuous Learning System initialized")

    def analyze_mistake(self, trade: TradeResult):
        """تحليل خطأ وتعلّم منه"""
        if trade.was_winner:
            return  # لا حاجة للتحليل

        # تحديد نوع الخطأ
        mistake_type = self._classify_mistake(trade)

        # تسجيل النمط
        if mistake_type not in self.error_patterns:
            self.error_patterns[mistake_type] = {
                'count': 0,
                'examples': [],
                'common_features': {}
            }

        pattern = self.error_patterns[mistake_type]
        pattern['count'] += 1
        pattern['examples'].append(trade)

        # تحديث الميزات المشتركة
        for key, value in trade.features.items():
            if key not in pattern['common_features']:
                pattern['common_features'][key] = []
            pattern['common_features'][key].append(value)

        # اتخاذ إجراء
        self._take_corrective_action(mistake_type, trade)

        logger.warning(f"📊 Mistake analyzed: {mistake_type}")

    def _classify_mistake(self, trade: TradeResult) -> str:
        """تصنيف نوع الخطأ"""
        features = trade.features

        if features.get('htf_trend_numeric', 0) == 0:
            return 'counter_trend_trade'

        if features.get('confluence_count', 0) < 3:
            return 'low_confluence'

        if features.get('is_kill_zone', 0) == 0:
            return 'wrong_time'

        if features.get('volume_ratio', 1) < 0.8:
            return 'low_volume'

        return 'unknown'

    def _take_corrective_action(self, mistake_type: str, trade: TradeResult):
        """اتخاذ إجراء تصحيحي"""
        actions = {
            'counter_trend_trade': 'Increase htf_trend weight',
            'low_confluence': 'Increase minimum confluence threshold',
            'wrong_time': 'Reduce position size outside kill zones',
            'low_volume': 'Add volume filter',
        }

        action = actions.get(mistake_type, 'General improvement')

        self.improvement_log.append({
            'timestamp': datetime.now(),
            'mistake_type': mistake_type,
            'action': action,
            'trade_id': trade.trade_id,
        })

        logger.info(f"🔧 Action taken: {action}")

    def get_insights(self) -> Dict:
        """الحصول على insights من الأخطاء"""
        return {
            'total_mistakes': sum(p['count'] for p in self.error_patterns.values()),
            'mistake_types': self.error_patterns,
            'improvements_applied': len(self.improvement_log),
            'top_mistake': max(
                self.error_patterns.items(),
                key=lambda x: x[1]['count'],
                default=(None, None),
            )[0] if self.error_patterns else None,
        }


# ════════════════════════════════════════════════════════════════
# 📊 Example Usage
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # إنشاء نموذج
    ml_model = TradingMLModel()
    learning_system = ContinuousLearningSystem(ml_model)

    # مثال: التعلم من صفقة
    trade_result = TradeResult(
        trade_id="TEST_001",
        symbol="BTC/USDT",
        timestamp=datetime.now(),
        features={
            'htf_trend_numeric': 1,
            'confluence_count': 5,
            'is_kill_zone': 1,
            'volume_ratio': 1.5,
        },
        predicted_score=75,
        predicted_confidence=0.8,
        actual_pnl=-50,
        actual_pnl_pct=-1.0,
        was_winner=False,
        htf_trend='bullish',
        pattern_type='liquidity_sweep',
        confluence_components={}
    )

    ml_model.learn_from_trade(trade_result)
    learning_system.analyze_mistake(trade_result)

    print("\n" + "=" * 60)
    print("🧠 ML System Demo Complete")
    print("=" * 60)
    print(f"📊 Performance: {ml_model.get_performance_report()}")
    print(f"💡 Insights: {learning_system.get_insights()}")
    print("=" * 60)
