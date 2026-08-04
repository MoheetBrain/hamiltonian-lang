-- There is a real y strictly greater than every real x. This is FALSE.
theorem no_greatest_real : ¬ (∃ y : ℝ, ∀ x : ℝ, y > x) := by
  rintro ⟨y, hy⟩
  exact absurd (hy (y + 1)) (by linarith)
