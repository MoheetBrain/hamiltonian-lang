-- Negation OUTSIDE the quantifier.
theorem not_all_pos : ¬ (∀ x : ℝ, x > 0) := by
  intro h
  exact absurd (h (-1)) (by norm_num)
