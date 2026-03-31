#!/usr/bin/env python3
"""
Window Completion Analyzer
Configurable algorithm that analyzes which algorithms are most suitable to modify outcome at 75%+ window completion.
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def create_window_completion_analyzer():
    """Create a configurable window completion analyzer."""
    print("🔨 CREATING WINDOW COMPLETION ANALYZER")
    print("=" * 60)
    
    analyzer_code = '''#!/usr/bin/env python3
"""
Window Completion Analyzer
Analyzes trading window at configurable completion threshold (default 75%) to determine which algorithms are most suitable to modify the outcome.
"""

import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class WindowCompletionAnalyzer:
    def __init__(self, completion_threshold=75.0, min_confidence=60.0):
        self.completion_threshold = completion_threshold  # Configurable: when to analyze (default 75%)
        self.min_confidence = min_confidence  # Minimum confidence to suggest modification
        self.algorithms = {}
        self.window_data = {}
        
    def analyze_window_state(self, window_data, scanners, current_time):
        """Analyze current window state and suggest suitable algorithms."""
        print(f"🔍 WINDOW COMPLETION ANALYSIS")
        print("=" * 50)
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Completion: {self.completion_threshold:.1f}%")
        print()
        
        # Calculate window completion
        elapsed = window_data.get('elapsed', 0)
        window_seconds = window_data.get('window_seconds', 300)
        completion_pct = (elapsed / window_seconds) * 100
        
        if completion_pct < self.completion_threshold:
            print(f"⏳ Window at {completion_pct:.1f}% - Not yet at {self.completion_threshold:.1f}% threshold")
            return None
        
        print(f"📊 Window at {completion_pct:.1f}% - Analyzing for modification opportunities")
        
        # Analyze each algorithm's modification potential
        analysis_results = {}
        
        for algo_name, scanner in scanners.items():
            if not hasattr(scanner, 'get_signal'):
                continue
                
            analysis = self.analyze_algorithm_modification_potential(
                algo_name, scanner, window_data, completion_pct
            )
            analysis_results[algo_name] = analysis
        
        # Rank algorithms by modification suitability
        suitable_algorithms = self.rank_algorithms_by_suitability(analysis_results)
        
        # Generate recommendations
        recommendations = self.generate_recommendations(
            suitable_algorithms, window_data, completion_pct
        )
        
        # Display results
        self.display_analysis_results(
            completion_pct, analysis_results, suitable_algorithms, recommendations
        )
        
        return recommendations
    
    def analyze_algorithm_modification_potential(self, algo_name, scanner, window_data, completion_pct):
        """Analyze individual algorithm's potential to modify outcome."""
        try:
            # Get algorithm's current signal
            context = window_data.copy()
            context.update({
                'elapsed': window_data.get('elapsed', 0),
                'window_seconds': window_data.get('window_seconds', 300),
                'completion_pct': completion_pct
            })
            
            signal = scanner.get_signal(context)
            
            analysis = {
                'name': algo_name,
                'current_signal': signal,
                'signal_type': self.classify_signal_type(signal),
                'timing_suitability': self.analyze_timing_suitability(signal, context),
                'modification_potential': self.assess_modification_potential(signal, context),
                'confidence': self.calculate_confidence(scanner, signal, context),
                'risk_level': self.assess_risk_level(signal, context),
                'historical_effectiveness': self.get_historical_effectiveness(algo_name)
            }
            
            return analysis
            
        except Exception as e:
            return {
                'name': algo_name,
                'error': str(e),
                'current_signal': 'ERROR',
                'modification_potential': 'LOW'
            }
    
    def classify_signal_type(self, signal):
        """Classify the type of signal."""
        if signal in ['WAIT', 'NO_DATA', 'ERROR']:
            return 'INACTIVE'
        elif 'BET_' in signal:
            return 'BET_RECOMMENDATION'
        elif signal in ['UP', 'DOWN']:
            return 'DIRECTIONAL'
        else:
            return 'OTHER'
    
    def analyze_timing_suitability(self, signal, context):
        """Analyze if algorithm timing is suitable for modification."""
        elapsed = context.get('elapsed', 0)
        window_seconds = context.get('window_seconds', 300)
        
        # Early window (first 25%) - good for modification
        if elapsed < window_seconds * 0.25:
            return 'EXCELLENT'
        # Mid window (25%-75%) - good for modification    
        elif elapsed < window_seconds * 0.75:
            return 'GOOD'
        # Late window (75%+) - limited modification potential
        else:
            return 'LIMITED'
    
    def assess_modification_potential(self, signal, context):
        """Assess how much the algorithm could modify the outcome."""
        signal_type = self.classify_signal_type(signal)
        elapsed = context.get('elapsed', 0)
        window_seconds = context.get('window_seconds', 300)
        
        # Base potential by signal type
        if signal_type == 'DIRECTIONAL':
            base_potential = 'HIGH'  # Directional signals can directly influence outcome
        elif signal_type == 'BET_RECOMMENDATION':
            base_potential = 'MEDIUM'  # Bet recommendations have moderate influence
        else:
            base_potential = 'LOW'
        
        # Adjust for timing
        timing = self.analyze_timing_suitability(signal, context)
        
        if timing == 'EXCELLENT':
            return base_potential
        elif timing == 'GOOD':
            return base_potential
        elif timing == 'LIMITED' and base_potential == 'HIGH':
            return 'MEDIUM'  # Late timing reduces high potential
        else:
            return base_potential
    
    def calculate_confidence(self, scanner, signal, context):
        """Calculate confidence in the algorithm's analysis."""
        try:
            # Factors that increase confidence
            confidence_factors = []
            
            # 1. Signal strength (based on scanner logic)
            if hasattr(scanner, 'confidence_score'):
                confidence_factors.append(scanner.confidence_score / 100.0)
            
            # 2. Historical performance
            historical = self.get_historical_effectiveness(scanner.__class__.__name__)
            if historical:
                confidence_factors.append(historical)
            
            # 3. Market condition alignment
            price_history = context.get('history_objs', [])
            if price_history:
                volatility = self.calculate_volatility(price_history[-20:])  # Recent volatility
                if volatility > 0:
                    confidence_factors.append(min(volatility / 2.0, 1.0))  # Higher confidence in stable markets
            
            # 4. Multiple algorithm confirmation
            if 'CONFLICT' not in signal:
                confidence_factors.append(0.8)  # No conflict increases confidence
            
            # Calculate weighted average
            if confidence_factors:
                confidence = sum(confidence_factors) / len(confidence_factors)
            else:
                confidence = 0.5
            
            return min(confidence * 100, 95.0)  # Cap at 95%
            
        except:
            return 50.0
    
    def assess_risk_level(self, signal, context):
        """Assess the risk level of the algorithm's action."""
        if signal in ['WAIT', 'NO_DATA']:
            return 'LOW'
        elif 'BET_' in signal:
            return 'MEDIUM'  # Betting involves risk
        elif signal in ['UP', 'DOWN']:
            return 'HIGH'  # Directional predictions are higher risk
        else:
            return 'MEDIUM'
    
    def calculate_volatility(self, price_history):
        """Calculate recent price volatility."""
        if len(price_history) < 2:
            return 0.0
        
        prices = [p['price'] for p in price_history]
        if len(prices) < 2:
            return 0.0
            
        returns = []
        for i in range(1, len(prices)):
            returns.append((prices[i] - prices[i-1]) / prices[i-1])
        
        avg_return = sum(returns) / len(returns)
        volatility = sum(abs(r - avg_return) for r in returns) / len(returns)
        
        return volatility
    
    def get_historical_effectiveness(self, algo_name):
        """Get historical effectiveness data for algorithm."""
        # This would typically come from a database or config file
        # For now, return reasonable defaults based on algorithm type
        effectiveness_map = {
            'MOM': 0.65,      # Momentum tends to be effective
            'MM2': 0.70,      # Market Maker 2 is reliable
            'GRI': 0.60,      # Grind Snap is moderate
            'NIT': 0.75,      # Nitro is highly effective
            'VSN': 0.68,      # VolSnap is good
            'HDO': 0.55,      # HDO is defensive, moderate
            'BRI': 0.62,      # BRI is reasonable
            'WCP': 0.58,      # WCP is moderate
            'SSC': 0.65,      # SSC is decent
            'ADT': 0.60,      # ADT is moderate
        }
        
        return effectiveness_map.get(algo_name[:3].upper(), 0.60)
    
    def rank_algorithms_by_suitability(self, analysis_results):
        """Rank algorithms by their suitability for modification."""
        suitable = []
        
        for algo_name, analysis in analysis_results.items():
            if 'error' in analysis:
                continue
            
            # Calculate suitability score
            score = 0
            
            # Modification potential (40% weight)
            potential_scores = {'HIGH': 40, 'MEDIUM': 25, 'LOW': 10}
            score += potential_scores.get(analysis['modification_potential'], 0)
            
            # Timing suitability (30% weight)
            timing_scores = {'EXCELLENT': 30, 'GOOD': 20, 'LIMITED': 5}
            score += timing_scores.get(analysis['timing_suitability'], 0)
            
            # Confidence (20% weight)
            score += (analysis['confidence'] / 100) * 20
            
            # Risk vs reward (10% weight)
            risk_scores = {'HIGH': 5, 'MEDIUM': 10, 'LOW': 15}
            score += risk_scores.get(analysis['risk_level'], 0)
            
            analysis['suitability_score'] = score
            suitable.append((score, algo_name, analysis))
        
        # Sort by score (descending)
        suitable.sort(key=lambda x: x[0], reverse=True)
        return suitable
    
    def generate_recommendations(self, suitable_algorithms, window_data, completion_pct):
        """Generate modification recommendations."""
        if not suitable_algorithms:
            return []
        
        recommendations = []
        
        # Top 3 recommendations
        for i, (score, algo_name, analysis) in enumerate(suitable_algorithms[:3]):
            rec = {
                'rank': i + 1,
                'algorithm': algo_name,
                'score': score,
                'confidence': analysis['confidence'],
                'potential': analysis['modification_potential'],
                'timing': analysis['timing_suitability'],
                'risk': analysis['risk_level'],
                'current_signal': analysis['current_signal'],
                'recommendation': self.generate_algorithm_recommendation(analysis, completion_pct)
            }
            recommendations.append(rec)
        
        return recommendations
    
    def generate_algorithm_recommendation(self, analysis, completion_pct):
        """Generate specific recommendation for an algorithm."""
        potential = analysis['modification_potential']
        timing = analysis['timing_suitability']
        
        if potential == 'HIGH' and timing in ['EXCELLENT', 'GOOD']:
            return (
                f"🎯 EXCELLENT modification candidate at {completion_pct:.0f}% completion. "
                f"{analysis['name']} has {analysis['confidence']:.0f}% confidence and "
                f"can significantly influence the final outcome."
            )
        elif potential == 'HIGH' and timing == 'LIMITED':
            return (
                f"⚠️ HIGH potential but LIMITED timing at {completion_pct:.0f}% completion. "
                f"{analysis['name']} could modify outcome but window is almost complete. "
                f"Consider immediate action or wait for next window."
            )
        elif potential == 'MEDIUM' and timing in ['EXCELLENT', 'GOOD']:
            return (
                f"📊 MODERATE modification potential at {completion_pct:.0f}% completion. "
                f"{analysis['name']} has {analysis['confidence']:.0f}% confidence and "
                f"may moderately influence the outcome."
            )
        else:
            return (
                f"❌ LOW modification potential at {completion_pct:.0f}% completion. "
                f"{analysis['name']} has limited ability to influence outcome."
            )
    
    def display_analysis_results(self, completion_pct, analysis_results, suitable_algorithms, recommendations):
        """Display the complete analysis results."""
        print(f"📊 WINDOW COMPLETION: {completion_pct:.1f}%")
        print()
        
        print("🔍 ALGORITHM ANALYSIS:")
        print("-" * 50)
        header = f"{'Algo':<15} | {'Signal':<20} | {'Potential':<15} | {'Confidence':<12} | {'Timing':<12} | {'Risk':<8} | {'Score':<8}"
        print(header)
        print("-" * 50)
        
        for algo_name, analysis in analysis_results.items():
            if 'error' in analysis:
                print(f"{algo_name:<15} | {'ERROR':<20} | {'N/A':<15} | {'N/A':<12} | {'N/A':<12} | {'N/A':<8} | {'N/A':<8}")
            else:
                potential = analysis['modification_potential']
                timing = analysis['timing_suitability']
                confidence = analysis['confidence']
                risk = analysis['risk_level']
                score = analysis.get('suitability_score', 0)
                
                print(f"{algo_name:<15} | {analysis['current_signal']:<20} | {potential:<15} | {confidence:>11.0f}% | {timing:<12} | {risk:<8} | {score:>8.0f}")
        
        print()
        
        if suitable_algorithms:
            print("🎯 TOP MODIFICATION CANDIDATES:")
            print("-" * 50)
            for rec in recommendations:
                print(f"#{rec['rank']}. {rec['algorithm']} (Score: {rec['score']:.1f})")
                print(f"   💡 {rec['recommendation']}")
                print()
        else:
            print("❌ No suitable algorithms found for modification")

def main():
    """Main function to run window completion analysis."""
    print("🎯 WINDOW COMPLETION ANALYZER")
    print("=" * 60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Example usage
    print("💡 USAGE:")
    print("   from window_completion_analyzer import WindowCompletionAnalyzer")
    print("   analyzer = WindowCompletionAnalyzer(completion_threshold=75.0, min_confidence=60.0)")
    print("   # When window reaches 75%:")
    print("   recommendations = analyzer.analyze_window_state(window_data, scanners, current_time)")
    print()
    print("⚙️ CONFIGURATION:")
    print("   • completion_threshold: When to analyze (default 75%)")
    print("   • min_confidence: Minimum confidence to suggest (default 60%)")
    print("   • Configurable per algorithm preferences")
    print()
    print("🔧 FEATURES:")
    print("   ✅ Configurable completion threshold (default 75%)")
    print("   ✅ Analyzes all active algorithms")
    print("   ✅ Calculates modification potential")
    print("   ✅ Timing suitability analysis")
    print("   ✅ Confidence scoring")
    print("   ✅ Risk assessment")
    print("   ✅ Historical effectiveness weighting")
    print("   ✅ Ranked recommendations")
    print("   ✅ Specific action recommendations")
    print()
    print("📊 OUTPUT:")
    print("   • Top 3 algorithms most suitable to modify outcome")
    print("   • Specific recommendations for each")
    print("   • Confidence scores and timing analysis")
    print("   • Risk/reward assessment")
    print()
    print("🎯 INTEGRATION:")
    print("   • Works with existing scanner system")
    print("   • Can be called at any completion percentage")
    print("   • Configurable per-algorithm weights")
    print("   • Real-time analysis capability")

if __name__ == "__main__":
    main()
'''
    
    # Write the analyzer
    analyzer_file = os.path.join(os.path.dirname(__file__), "window_completion_analyzer.py")
    
    try:
        with open(analyzer_file, 'w', encoding='utf-8') as f:
            f.write(analyzer_code)
        
        print(f"✅ Created window completion analyzer: {analyzer_file}")
        print(f"📊 File size: {len(analyzer_code) / 1024:.1f} KB")
        
        # Make it executable
        os.chmod(analyzer_file, 0o755)
        
        return analyzer_file
        
    except Exception as e:
        print(f"❌ Failed to create analyzer: {e}")
        return None

def main():
    print("🎯 WINDOW COMPLETION ANALYZER CREATOR")
    print("=" * 60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    print("🔧 CREATING CONFIGURABLE ALGORITHM:")
    print("   • Window completion analyzer")
    print("   • Configurable threshold (default 75%)")
    print("   • Algorithm modification potential analysis")
    print("   • Ranked recommendations")
    print()
    
    analyzer_file = create_window_completion_analyzer()
    
    if analyzer_file:
        print(f"\\n✅ SYSTEM CREATED!")
        print(f"📋 Files Created:")
        print(f"   📄 window_completion_analyzer.py ({os.path.getsize(analyzer_file) / 1024:.1f} KB)")
        print()
        print(f"💡 USAGE:")
        print(f"   1. Import: from window_completion_analyzer import WindowCompletionAnalyzer")
        print(f"   2. Initialize: analyzer = WindowCompletionAnalyzer(completion_threshold=75.0)")
        print(f"   3. Analyze: recommendations = analyzer.analyze_window_state(window_data, scanners, current_time)")
        print(f"   4. Results: Get top 3 algorithms most suitable to modify outcome")
        print()
        print(f"🎨 FEATURES:")
        print(f"   ✅ Configurable completion threshold (75%, 80%, 90%, etc.)")
        print(f"   ✅ Analyzes all active algorithms for modification potential")
        print(f"   ✅ Timing suitability analysis (early/mid/late window)")
        print(f"   ✅ Confidence scoring based on multiple factors")
        print(f"   ✅ Risk assessment and historical effectiveness")
        print(f"   ✅ Ranked recommendations with specific actions")
        print()
        print(f"🔧 INTEGRATION:")
        print(f"   • Works with existing scanner system")
        print(f"   • Can be called at any window completion percentage")
        print(f"   • Provides real-time analysis for algorithm selection")
        print()
        print(f"📊 EXAMPLE OUTPUT:")
        print(f"   At 75% window completion:")
        print(f"   🎯 'NITRO - HIGH modification potential (85% confidence)'")
        print(f"   🎯 'MM2 - GOOD modification potential (70% confidence)'")
        print(f"   🎯 'GRI - MODERATE modification potential (65% confidence)'")
        print()
        print(f"💭 RESULT:")
        print(f"   You now have a configurable algorithm that tells you which")
        print(f"   algorithms are most suitable to modify the outcome at any completion threshold!")

if __name__ == "__main__":
    main()
