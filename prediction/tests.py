from django.test import TestCase

from prediction.grid_utils import filter_heatmap_points


class HeatmapFilterTests(TestCase):
    def _point(
        self,
        *,
        prediction: int = 0,
        risk_score: float = 0.0,
        density: float = 0.0,
        confidence: float = 0.99,
        mean_degree_danger: float = 0.0,
    ) -> dict:
        return {
            "prediction": prediction,
            "risk_score": risk_score,
            "density": density,
            "confidence": confidence,
            "mean_degree_danger": mean_degree_danger,
        }

    def test_hides_confident_low_risk_without_local_signal(self):
        """Évite l'inondation verte (confiance haute sur toute la grille)."""
        flood = [
            self._point(prediction=0, confidence=0.98, risk_score=0.03)
            for _ in range(100)
        ]
        self.assertEqual(filter_heatmap_points(flood), [])

    def test_shows_elevated_and_moderate_predictions(self):
        points = [
            self._point(prediction=2, risk_score=1.0, confidence=0.97),
            self._point(prediction=1, risk_score=0.55, confidence=0.98),
        ]
        self.assertEqual(len(filter_heatmap_points(points)), 2)

    def test_shows_local_history_only_with_real_danger(self):
        hidden = self._point(
            prediction=0,
            density=1.0,
            confidence=0.99,
            risk_score=0.03,
            mean_degree_danger=0.0,
        )
        visible = self._point(
            prediction=0,
            density=1.0,
            confidence=0.99,
            risk_score=0.25,
            mean_degree_danger=0.0,
        )
        filtered = filter_heatmap_points([hidden, visible])
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["risk_score"], 0.25)
