-- Uniform continuity, with the quantifier prefix written out.
def UniformlyContinuous (f : ℝ → ℝ) : Prop :=
  ∀ ε : ℝ, ε > 0 → ∃ δ : ℝ, δ > 0 ∧ ∀ u : ℝ, ∀ v : ℝ,
    |u - v| < δ → |f u - f v| < ε
