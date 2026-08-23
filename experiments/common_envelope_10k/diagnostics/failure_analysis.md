# Common-envelope failure analysis

Generated automatically because delta < +15pp.

- HML predictions changed: 281
- Neutral predictions changed: 1408

## Changed-row aggregates

```json
{
  "hml": {
    "n": 281,
    "depth": {
      "2-3": 78,
      "1": 66,
      "11-20": 39,
      "4-5": 35,
      "6-10": 49,
      "21+": 14
    },
    "complexity": {
      "LOW": 76,
      "HIGH": 69,
      "MEDIUM": 62,
      "VERY_HIGH": 74
    },
    "tactic_family_top20": [
      [
        "intro",
        27
      ],
      [
        "rintro",
        24
      ],
      [
        "rw",
        22
      ],
      [
        "ext",
        21
      ],
      [
        "exact",
        19
      ],
      [
        "simp",
        19
      ],
      [
        "refine",
        11
      ],
      [
        "dsimp",
        8
      ],
      [
        "rfl",
        8
      ],
      [
        "have",
        7
      ],
      [
        "simpa",
        7
      ],
      [
        "rcases",
        6
      ],
      [
        "infer_instance",
        6
      ],
      [
        "let",
        5
      ],
      [
        "apply",
        5
      ],
      [
        "aesop",
        5
      ],
      [
        "cases",
        4
      ],
      [
        "obtain",
        4
      ],
      [
        "simp_all",
        3
      ],
      [
        "norm_cast",
        3
      ]
    ],
    "gold_position": {
      "4": 43,
      "5": 67,
      "3": 35,
      "1": 51,
      "2": 47,
      "0": 38
    },
    "lexical_correct": 85,
    "mean_hml_tokens": 470.7544483985765,
    "mean_neutral_tokens": 373.4519572953737
  },
  "neutral": {
    "n": 1408,
    "depth": {
      "1": 346,
      "4-5": 197,
      "2-3": 388,
      "6-10": 224,
      "11-20": 178,
      "21+": 75
    },
    "complexity": {
      "LOW": 374,
      "MEDIUM": 344,
      "HIGH": 323,
      "VERY_HIGH": 367
    },
    "tactic_family_top20": [
      [
        "rw",
        247
      ],
      [
        "simp",
        177
      ],
      [
        "exact",
        161
      ],
      [
        "refine",
        73
      ],
      [
        "rintro",
        65
      ],
      [
        "have",
        64
      ],
      [
        "intro",
        63
      ],
      [
        "ext",
        50
      ],
      [
        "apply",
        36
      ],
      [
        "simpa",
        33
      ],
      [
        "obtain",
        29
      ],
      [
        "rcases",
        29
      ],
      [
        "rfl",
        29
      ],
      [
        "let",
        23
      ],
      [
        "dsimp",
        23
      ],
      [
        "rwa",
        20
      ],
      [
        "simp_rw",
        19
      ],
      [
        "cases",
        18
      ],
      [
        "use",
        14
      ],
      [
        "congr",
        10
      ]
    ],
    "gold_position": {
      "0": 205,
      "1": 218,
      "5": 252,
      "3": 246,
      "4": 249,
      "2": 238
    },
    "lexical_correct": 638,
    "mean_hml_tokens": 483.79829545454544,
    "mean_neutral_tokens": 390.81107954545456
  }
}
```

## Deterministic diagnostic samples

Largest HML regressions: `['H50K-LEAN-0140f21681993b87', 'H50K-LEAN-05f2816c607e13ab', 'H50K-LEAN-06cba2af851a078a', 'H50K-LEAN-09a87055aab504c7', 'H50K-LEAN-0e4e70f92db10de1', 'H50K-LEAN-10350f47b370c879', 'H50K-LEAN-138e10512c63683f', 'H50K-LEAN-13915383bb03b712', 'H50K-LEAN-1b460a7fb94099b1', 'H50K-LEAN-1fc325b67ebbc406', 'H50K-LEAN-208c62fe73fce904', 'H50K-LEAN-267b253ca63a228a', 'H50K-LEAN-2a2fb675a09381c4', 'H50K-LEAN-2b8ac2d980907cc9', 'H50K-LEAN-2da656f75935ed67', 'H50K-LEAN-3d28424eb5e58736', 'H50K-LEAN-45f73d0b18d0ed6b', 'H50K-LEAN-477079733e3d18cb', 'H50K-LEAN-4867922fb018dc90', 'H50K-LEAN-48a267d801ad3b51', 'H50K-LEAN-48dab72201550572', 'H50K-LEAN-4b01b43bfa3c7501', 'H50K-LEAN-4d67a92927afa8a6', 'H50K-LEAN-56aa52607148f8ff', 'H50K-LEAN-56fb520482c35003']`

Largest Neutral improvements: `['H50K-LEAN-0012473c73800d33', 'H50K-LEAN-006de756313bdaa1', 'H50K-LEAN-007a08e2b0821e78', 'H50K-LEAN-00b7ccc74df475b9', 'H50K-LEAN-01254ec8ddc660ff', 'H50K-LEAN-01718a9ab64f95bf', 'H50K-LEAN-01b9b996063af1fa', 'H50K-LEAN-01d4518564bf4ad8', 'H50K-LEAN-024fc39d9b7a8513', 'H50K-LEAN-02cab228165b50cf', 'H50K-LEAN-02ce04cccd8dc0e3', 'H50K-LEAN-0335baa85808af70', 'H50K-LEAN-036e51a23f7962e4', 'H50K-LEAN-0408dfec580d91d8', 'H50K-LEAN-044c071daaa60e86', 'H50K-LEAN-046f1d72453b743d', 'H50K-LEAN-0488016a7591e120', 'H50K-LEAN-04d20a11d81c51f2', 'H50K-LEAN-054ba7a7c1656c4b', 'H50K-LEAN-05936d43fffad2de', 'H50K-LEAN-061754750a3ba4b9', 'H50K-LEAN-06202eef71954f67', 'H50K-LEAN-067b0853d6800c39', 'H50K-LEAN-0681a03faca58b54', 'H50K-LEAN-06cba2af851a078a']`
