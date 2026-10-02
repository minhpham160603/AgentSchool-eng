import re
import random
import copy

# ========= Chinese numeral compatibility utilities =========
CN_NUM = {
    "\u96f6": 0, "\u3007": 0, "\u4e00": 1, "\u4e8c": 2, "\u4e24": 2, "\u4e09": 3,
    "\u56db": 4, "\u4e94": 5, "\u516d": 6, "\u4e03": 7, "\u516b": 8, "\u4e5d": 9
}
CN_UNIT = {"\u5341": 10, "\u767e": 100, "\u5343": 1000, "\u4e07": 10000, "\u4ebf": 100000000}

def chinese_to_arabic(cn: str) -> int:
    unit = 0
    ldig = []
    for c in reversed(cn):
        if c in CN_UNIT:
            unit = CN_UNIT[c]
            if unit in (10000, 100000000):
                ldig.append(unit)
                unit = 1
        else:
            dig = CN_NUM.get(c, None)
            if dig is not None:
                if unit:
                    dig *= unit
                    unit = 0
                ldig.append(dig)
    if unit == 10:
        ldig.append(10)
    val, tmp = 0, 0
    for x in reversed(ldig):
        if x in (10000, 100000000):
            tmp *= x
            val += tmp
            tmp = 0
        else:
            tmp += x
    return val + tmp

def arabic_to_chinese(num: int) -> str:
    units = ["", "\u5341", "\u767e", "\u5343"]
    nums = "\u96f6\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d"
    if num == 0: return "\u96f6"
    s, unit_pos = "", 0
    while num > 0:
        num, rem = divmod(num, 10)
        if rem != 0:
            s = nums[rem] + units[unit_pos] + s
        elif not s.startswith("\u96f6"):
            s = "\u96f6" + s
        unit_pos += 1
    return s.strip("\u96f6")

NUM_PATTERN = re.compile(r'(\d+(?:\.\d+)?)|([\u96f6\u3007\u4e00\u4e8c\u4e24\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e\u5343\u4e07\u4ebf]+)')

def extract_numbers(text):
    """Return each number as (original text, numeric value, is Chinese numeral)."""
    results = []
    for m in NUM_PATTERN.finditer(text or ""):
        if m.group(1):
            results.append((m.group(1), float(m.group(1)), False))
        elif m.group(2):
            val = chinese_to_arabic(m.group(2))
            results.append((m.group(2), val, True))
    return results

def replace_first_number(text, fn):
    """Replace the first Arabic or Chinese numeral using the supplied function."""
    def repl(m):
        if m.group(1):  # Arab
            val = float(m.group(1))
            new_val = fn(val)
            # Securely handle float-point conversions
            try:
                if isinstance(new_val, (int, float)) and float(new_val).is_integer():
                    return str(int(float(new_val)))
                else:
                    return str(new_val)
            except (ValueError, TypeError):
                return str(new_val)
        else:  # Chinese
            val = chinese_to_arabic(m.group(2))
            new_val = fn(val)
            if isinstance(new_val, float) and not float(new_val).is_integer():
                return str(new_val)
            # Convert safely to integer
            try:
                new_val_int = int(float(new_val))
                if new_val_int < 10000 and random.random() < 0.5:
                    return arabic_to_chinese(new_val_int)
                return str(new_val_int)
            except (ValueError, TypeError):
                return str(new_val)
    return NUM_PATTERN.sub(repl, text, count=1)


# ========= Question modifier =========
class PersonalizedQuestionModifier:
    def __init__(self, student, base_prob=0.35, seed=None):
        self.student = student
        self.mistake_levels = self._analyze_student_mistakes()
        self.base_prob = base_prob
        if seed is not None:
            random.seed(seed)

    # --------- Analyze the student's mistake profile ---------
    def _analyze_student_mistakes(self):
        texts = [str(t).casefold() for t in getattr(self.student.scratch, "common_mistakes", [])]
        levels = {
            "careless_calculation": 0,
            "concept_confusion": 0,
            "shallow_understanding": 0,
            "overconfidence": 0,
            "impatience": 0,
            "surface_reading": 0
        }
        def bump(key, val): levels[key] = max(levels[key], val)

        for s in texts:
            if any(k in s for k in ("skip", "careless", "does not check", "don't check", "do not check", "calculation error", "unit", "substitution")):
                bump("careless_calculation", 3)
            if any(k in s for k in ("minor error", "small mistake", "detail")):
                bump("careless_calculation", 1)
            if any(k in s for k in ("confusion", "formula", "concept")):
                bump("concept_confusion", 3)
            if any(k in s for k in ("surface", "shallow", "ignores principles", "ignoring principles", "lacks causal reasoning", "lack of causal reasoning")):
                bump("shallow_understanding", 2)
            if any(k in s for k in ("overconfident", "overconfidence", "does not check", "intuition")):
                bump("overconfidence", 2)
            if any(k in s for k in ("gives up", "give up", "lacks persistence", "hesitates", "stuck halfway")):
                bump("impatience", 2)
            if any(k in s for k in ("keyword", "ignores context", "ignore context", "one-sided", "selective reading")):
                bump("surface_reading", 3)
        return levels

    # --------- Decide whether to modify a question ---------
    def should_modify_question(self, question_index):
        active = sum(1 for v in self.mistake_levels.values() if v > 0)
        prob = min(0.15 + 0.1*active + 0.05*max(self.mistake_levels.values()), 0.85)
        return random.random() < max(self.base_prob, prob)

    # --------- Main entrance ---------
    def modify_question(self, question_data, question_index):
        if not self.should_modify_question(question_index):
            return question_data
        q = copy.deepcopy(question_data)

        # Protect key fields from unexpected changes
        protected_fields = {
            "index": q.get("index"),
            "embedding": q.get("embedding"),
            "answer": q.get("answer"),  # Save answer fields
            "question_id": q.get("question_id"),  # Protection issues ID
            "id": q.get("id"),  # Protection ID Fields
        }

        applied = []
        L = self.mistake_levels
        if L["careless_calculation"] > 0: self._calc_traps(q,L["careless_calculation"]); applied.append("calc_traps")
        if L["concept_confusion"] > 0: self._concept_traps(q,L["concept_confusion"]); applied.append("concept_traps")
        if L["overconfidence"] > 0: self._overconfidence_traps(q,L["overconfidence"]); applied.append("overconfidence_traps")
        if L["impatience"] > 0: self._impatience_traps(q,L["impatience"]); applied.append("impatience_traps")
        if L["surface_reading"] > 0: self._reading_traps(q,L["surface_reading"]); applied.append("reading_traps")
        if L["shallow_understanding"] > 0: self._shallow_traps(q,L["shallow_understanding"]); applied.append("shallow_traps")

        # Restore protected fields
        for field, value in protected_fields.items():
            if value is not None:
                q[field] = value

        q.setdefault("modification_info", {})
        q["modification_info"].update({
            "applied": applied,
            "levels": {k:v for k,v in self.mistake_levels.items() if v},
        })
        return q

    # --------- Tool Functions ---------
    def _numbers(self, text):
        return extract_numbers(text)

    def _replace_first_number(self, text, fn):
        return replace_first_number(text, fn)

    def _ensure_options(self, q):
        if "options" not in q or not isinstance(q["options"], list): q["options"] = []
        return q["options"]

    def _inject_rounding_rule(self, q, rule):
        q["content"] = (q.get("content","").rstrip() +
            f"\nResponse requirements: Give the final result to {rule['sf']} significant figures, include the unit {rule['unit']}, and use {rule['dp']} decimal places.")

    def _add_numeric_distractors(self, q, base=None, count=2):
        opts = self._ensure_options(q)
        target = None
        if isinstance(q.get("answer"), (int,float,str)):
            try: target = float(q["answer"])
            except: pass
        if target is None:
            nums = self._numbers(q.get("content",""))
            if nums:
                try: target = float(nums[0][1])
                except: pass
        if target is None and base is not None: target = base
        if target is None: return
        near = [target*(1+x) for x in [0.1,-0.1,0.01,-0.01,0.5,-0.5]]
        random.shuffle(near)
        for v in near[:count]:
            s = self._fmt_number(v)
            if s not in opts: opts.append(s)

    def _fmt_number(self, x):
        try:
            # Avoid scientific algorithms and use fixed formats for large or small numbers
            val = float(x)
            if abs(val) >= 1e6 or (abs(val) < 1e-3 and val != 0):
                # For large or very small numbers, rounded to a reasonable range
                if abs(val) >= 1e6:
                    val = round(val / 1e6) * 1e6  # To millions
                else:
                    val = round(val, 3)  # Keep decimals 3 bit

            # Use a fixed format to avoid scientific counting
            if abs(val - round(val)) < 1e-10:  # More rigorous integer judgement
                return str(int(round(val)))
            else:
                # Ensure that decimal formats are not misinterpreted as integers
                formatted = f"{val:.6f}".rstrip('0').rstrip('.')
                # If formatted to look integer, add.0 Postfix to specify
                if '.' not in formatted and abs(val - round(val)) > 1e-10:
                    formatted += '.0'
                return formatted
        except (ValueError, TypeError):
            return str(x)

    # --------- All dimensions trap (example retained)） ---------
    def _calc_traps(self, q, level):
        c = q.get("content","")
        nums = self._numbers(c)
        if not nums: return
        if level >= 1:
            def near_miss(v): return self._fmt_number(v + random.choice([1,-1,0.1,-0.1]))
            q["content"] = self._replace_first_number(c, near_miss)
        if level >= 2:
            self._inject_rounding_rule(q, {"sf":2,"unit":"kg","dp":2})
            q["content"] += "\nAlso account for an additional 5% loss during the process, if relevant."
        if level >= 3:
            def transpose(v): return self._fmt_number(v*10)
            q["content"] = self._replace_first_number(q["content"], transpose)
        self._add_numeric_distractors(q, count=3)

    def _concept_traps(self, q, level):
        c = q.get("content","")
        # Replace related quantities or add a competing quantity to the question.
        swaps = [
            ("area", "perimeter"),
            ("speed", "time"),
            ("volume", "surface area"),
            ("density", "mass"),
            ("Power", "Energy"),
        ]
        candidates = [p for p in swaps if p[0] in c] + [ (b,a) for (a,b) in swaps if b in c ]
        if candidates:
            a,b = random.choice(candidates)
            if level >= 1:
                # In the same way: there are two words simultaneously to create the ambiguity of which is the question
                q["content"] = re.sub(a, f"{a} (related quantity: {b})", c, count=1, flags=re.IGNORECASE)
            if level >= 2:
                # Directly changing the question method target (absorption of the error formula)）
                q["content"] = re.sub(r"(Please|Calculate).*?$", lambda m: m.group(0).replace(a, b), q["content"], count=1, flags=re.M)
            if level >= 3:
                # Add data matching wrong concepts (e.g., give perimeter data to solve area issues)）
                q["content"] += "\nAdditional information: The total boundary length was also measured."

        # Option Interference: Gives an order of magnitude to an "incorrect formulae product" (unable to calculate an approximate order of magnitude)）
        self._add_numeric_distractors(q, count=2)

    def _overconfidence_traps(self, q, level):
        # Add two plausible, closely matched answer choices and any special formatting requirements.
        if level >= 1:
            self._add_numeric_distractors(q, count=2)
        if level >= 2:
            q["content"] += "\nGive your final answer in scientific notation."
        if level >= 3:
            # It's like naming the middle（x and χ、l and 1）
            q["content"] = q["content"].replace("x", random.choice(["χ","x"]), 1).replace("l", "1", 1)

    def _impatience_traps(self, q, level):
        # Long background + Critical conditions buried in the middle
        pre = ("A routine survey recorded several sets of data and observation notes, "
               "including temperature changes, equipment IDs, and readings from an unrelated control group.")
        key = "Note: Use only valid data from the second measurement."
        if level >= 1:
            q["content"] = pre + "\n" + q.get("content","")
        if level >= 2:
            mid_inject_at = max(0, len(q["content"])//2)
            q["content"] = q["content"][:mid_inject_at] + key + q["content"][mid_inject_at:]
        if level >= 3:
            q["content"] += "\nHint: The first set of timestamps is inconsistent; use the second record."

    def _reading_traps(self, q, level):
        c = q.get("content","")
        # Polar Flip: Correct↔Incorrect; including↔Excluded; most likely↔Most likely
        flips = [
            (r"(Which one?.*?)(Correct)", r"\1 Wrong"),
            (r"(Below.*?)(Including)", r"\1 Excluded"),
            (r"(Most)(Maybe)", r"\1 Impossible")
        ]
        if level >= 1:
            for pat, rep in flips:
                if re.search(pat, c):
                    c = re.sub(pat, rep, c, count=1)
                    break
            q["content"] = c
        if level >= 2:
            # Disclaimer and exception
            q["content"] += "\nNote: Consider whether any exceptions apply."
        if level >= 3:
            # Insert two offset paragraphs
            q["content"] += "\nNote: The sample includes adults, but minors make up most of the group."

        # Arts category: one-sided expression of the "key word type" for options
        opts = self._ensure_options(q)
        if opts and level >= 1:
            fragment = random.choice(["Based on title only", "Just the first sentence", "Key words not relevant to context"])
            opts.append(f"{fragment}")

    def _shallow_traps(self, q, level):
        # Expression Transform + The steps are broken + Remove the obvious label
        if level >= 1:
            q["content"] = q.get("content","").replace("Known", "Alleged").replace("Certification", "explanation")
        if level >= 2:
            # Exchange the order of two terms
            parts = re.split(r'[。；;]\s*', q["content"])
            if len(parts) >= 3:
                i, j = 0, 1
                parts[i], parts[j] = parts[j], parts[i]
                q["content"] = "。".join(parts)
        if level >= 3:
            # Remove the formula name and leave only a hint of variable relationships
            q["content"] = re.sub(r"([A-Za-zαβγΔΣπ]+)\s*=", r"\1≈", q["content"])
