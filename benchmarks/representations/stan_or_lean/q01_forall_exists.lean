-- For every real x there is a real y strictly greater than x.
theorem forall_exists_greater : ∀ x : ℝ, ∃ y : ℝ, y > x := by
  intro x
  exact ⟨x + 1, by linarith⟩
