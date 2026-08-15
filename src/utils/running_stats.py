"""
Running Statistics Module
Implements Welford's online algorithm for incremental statistical calculations.
Replaces O(n) batch calculations with O(1) incremental updates.
"""
import math
from typing import Dict, Any


class RunningStats:
    """
    Welford's online algorithm for computing running mean, variance, skewness, and kurtosis.
    
    Benefits:
    - O(1) time complexity per update (vs O(n) for batch recalculation)
    - O(1) space complexity (no need to store samples)
    - Numerically stable
    - Perfect for telemetry and monitoring scenarios
    """
    
    __slots__ = ('n', 'mean', 'M2', 'M3', 'M4', '_min_val', '_max_val')
    
    def __init__(self):
        self.n: int = 0
        self.mean: float = 0.0
        self.M2: float = 0.0  # Sum of squares of differences from current mean
        self.M3: float = 0.0  # For skewness
        self.M4: float = 0.0  # For kurtosis
        self._min_val: float = float('inf')
        self._max_val: float = float('-inf')
    
    def update(self, x: float) -> None:
        """Update statistics with a new value in O(1) time."""
        n1 = self.n
        self.n += 1
        delta = x - self.mean
        delta_n = delta / self.n if self.n > 0 else 0.0
        delta_n2 = delta_n * delta_n
        term1 = delta * delta_n * n1
        
        self.mean += delta_n
        self.M4 += (
            term1 * delta_n2 * (n1 * n1 - 3 * n1 + 3) +
            6 * delta_n2 * self.M2 -
            4 * delta_n * self.M3
        )
        self.M3 += term1 * delta_n * (n1 - 2) - 3 * delta_n * self.M2
        self.M2 += term1
        
        # Track min/max
        if x < self._min_val:
            self._min_val = x
        if x > self._max_val:
            self._max_val = x
    
    def variance(self, population: bool = True) -> float:
        """Return variance (population by default, sample if population=False)."""
        if self.n == 0:
            return 0.0
        if population:
            return self.M2 / self.n
        return self.M2 / (self.n - 1) if self.n > 1 else 0.0
    
    def stddev(self, population: bool = True) -> float:
        """Return standard deviation."""
        return math.sqrt(self.variance(population))
    
    def skewness(self) -> float:
        """Return skewness (measure of asymmetry)."""
        if self.n > 2 and self.M2 > 0:
            return math.sqrt(self.n) * self.M3 / (self.M2 ** 1.5)
        return 0.0
    
    def kurtosis(self) -> float:
        """Return kurtosis (measure of tail heaviness)."""
        if self.n > 3 and self.M2 > 0:
            return (self.n * self.M4) / (self.M2 ** 2)
        return 0.0
    
    def excess_kurtosis(self) -> float:
        """Return excess kurtosis (kurtosis - 3, normalized to Gaussian)."""
        return self.kurtosis() - 3.0
    
    def cv(self) -> float:
        """Return coefficient of variation (stddev / mean)."""
        if self.mean > 0:
            return self.stddev() / self.mean
        return 0.0
    
    def min(self) -> float:
        """Return minimum value seen."""
        return self._min_val if self.n > 0 else 0.0
    
    def max(self) -> float:
        """Return maximum value seen."""
        return self._max_val if self.n > 0 else 0.0
    
    def range(self) -> float:
        """Return range (max - min)."""
        return self._max_val - self._min_val if self.n > 0 else 0.0
    
    def reset(self) -> None:
        """Reset all statistics."""
        self.n = 0
        self.mean = 0.0
        self.M2 = 0.0
        self.M3 = 0.0
        self.M4 = 0.0
        self._min_val = float('inf')
        self._max_val = float('-inf')
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Return all statistics as a dictionary."""
        return {
            'count': self.n,
            'mean': round(self.mean, 4),
            'variance': round(self.variance(), 4),
            'stddev': round(self.stddev(), 4),
            'skewness': round(self.skewness(), 4),
            'kurtosis': round(self.kurtosis(), 4),
            'excess_kurtosis': round(self.excess_kurtosis(), 4),
            'cv': round(self.cv(), 4),
            'min': round(self.min(), 4),
            'max': round(self.max(), 4),
            'range': round(self.range(), 4),
        }


class RunningPercentile:
    """
    Approximate percentile tracking using P² algorithm.
    More memory-efficient than storing all samples for percentile calculations.
    """
    
    def __init__(self, percentile: float = 0.95):
        self.p = percentile
        self.n = [0, 1, 2, 3, 4]  # Marker positions
        self.q = [0.0] * 5  # Marker heights (quantiles)
        self.n_prime = [0.0] * 5  # Desired marker positions
        self.dn = [0.0] * 5  # Increments for desired positions
        self.count = 0
        self.initialized = False
        self.init_buffer = []
    
    def update(self, x: float) -> None:
        """Update percentile estimate with new observation."""
        self.count += 1
        
        if not self.initialized:
            self.init_buffer.append(x)
            if len(self.init_buffer) >= 5:
                self._initialize()
            return
        
        # Find cell k such that q[k-1] <= x < q[k]
        if x < self.q[0]:
            self.q[0] = x
            k = 1
        elif x >= self.q[4]:
            self.q[4] = x
            k = 4
        else:
            k = 1
            for i in range(1, 5):
                if x < self.q[i]:
                    k = i
                    break
        
        # Increment positions of markers k+1 to 5
        for i in range(k, 5):
            self.n[i] += 1
        
        # Update desired positions and increments
        for i in range(5):
            self.n_prime[i] += self.dn[i]
        
        # Adjust marker heights if necessary
        for i in range(1, 4):
            d = self.n_prime[i] - self.n[i]
            if (d >= 1 and self.n[i + 1] - self.n[i] > 1) or \
               (d <= -1 and self.n[i - 1] - self.n[i] < -1):
                d_sign = 1 if d > 0 else -1
                q_new = self._parabolic(i, d_sign)
                
                if self.q[i - 1] < q_new < self.q[i + 1]:
                    self.q[i] = q_new
                else:
                    self.q[i] = self._linear(i, d_sign)
                
                self.n[i] += d_sign
    
    def _initialize(self) -> None:
        """Initialize markers with first 5 observations."""
        self.init_buffer.sort()
        self.q = self.init_buffer[:5].copy()
        self.n = [1, 2, 3, 4, 5]
        self.n_prime = [1, 1 + 2 * self.p, 1 + 4 * self.p, 3 + 2 * self.p, 5]
        self.dn = [0, self.p / 2, self.p, (1 + self.p) / 2, 1]
        self.initialized = True
        self.init_buffer = []
    
    def _parabolic(self, i: int, d: int) -> float:
        """Parabolic (P²) formula for marker adjustment."""
        qi = self.q[i]
        qim1 = self.q[i - 1]
        qip1 = self.q[i + 1]
        ni = self.n[i]
        nim1 = self.n[i - 1]
        nip1 = self.n[i + 1]
        
        term1 = d / (nip1 - nim1)
        term2 = (ni - nim1 + d) * (qip1 - qi) / (nip1 - ni)
        term3 = (nip1 - ni - d) * (qi - qim1) / (ni - nim1)
        
        return qi + term1 * (term2 + term3)
    
    def _linear(self, i: int, d: int) -> float:
        """Linear formula for marker adjustment."""
        qi = self.q[i]
        qid = self.q[i + d] if i + d < 5 else self.q[4]
        ni = self.n[i]
        nid = self.n[i + d] if i + d < 5 else self.n[4]
        
        return qi + d * (qid - qi) / (nid - ni)
    
    def percentile(self) -> float:
        """Return current percentile estimate."""
        if not self.initialized:
            if not self.init_buffer:
                return 0.0
            sorted_buf = sorted(self.init_buffer)
            idx = int(len(sorted_buf) * self.p)
            return sorted_buf[min(idx, len(sorted_buf) - 1)]
        return self.q[2]  # Middle marker is our percentile estimate
    
    def reset(self) -> None:
        """Reset percentile tracker."""
        self.count = 0
        self.initialized = False
        self.init_buffer = []
        self.n = [0, 1, 2, 3, 4]
        self.q = [0.0] * 5
        self.n_prime = [0.0] * 5
        self.dn = [0.0] * 5
