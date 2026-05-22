# **Why Your Attribution Numbers Never Match**

## **The Discrepancy Anatomy**

You open Skeldir and see it: **Meta Ads revenue is 16% lower than what Meta claims.**  
Not 2%. Not “rounding.” **Sixteen.** Enough to change which channel gets funded next week.

In that moment, your job quietly shifts. You’re no longer just “running campaigns.” You’re standing between two competing stories about reality—one told by an ad platform, one told by the money.

This guide gives you a mental model that turns that uneasy gap into something you can **name, explain, and act on**—without calling support.

**After reading this, you’ll be able to:**

* Explain why the mismatch happens (in plain language).  
* Sort it into the *few* root causes that actually matter.  
* Run a 10-minute checklist and produce a CFO-ready explanation.

---

## **The first rule: you are not looking at one truth—you're looking at two truths**

When Meta says “$50K revenue,” it’s not claiming **cash-in-bank**. It’s claiming **credit**: “We believe your ads caused this much revenue, using our rules.”

When Skeldir shows “$42K verified,” it’s anchoring to a **system-of-record**: payments and orders that actually cleared (think Stripe/processor truth). That is not “marketing influence.” That’s **accounting reality**.

So a discrepancy is not automatically a defect. It’s often the *shadow* cast by two systems measuring two different things, with two different rules, from two different vantage points.

The ad industry has been forced into this split reality because measurement is increasingly constrained by privacy, consent choices, and signal loss—meaning platforms and tools lean more on modeling and inference rather than direct observation. ([IAB](https://www.iab.com/wp-content/uploads/2024/03/IAB-State-of-Data-2024.pdf?utm_source=chatgpt.com))

---

## **Discrepancy isn’t random. It usually comes from one (or more) of these five mechanisms.**

If you can classify the mismatch, you can stop arguing with the dashboard and start making decisions again.

### **Mechanism 1 — Double counting across platforms (the “two platforms, one sale” problem)**

A single customer sees a Meta ad, later clicks a Google ad, then buys.

Meta wants credit. Google wants credit. Sometimes GA4 wants credit too.

Each system is not lying; each is measuring “influence” from its own universe. But when you sum those credits, you can exceed the real revenue. That excess doesn’t mean you invented money—it means you invented **overlapping explanations**.

**Clues this is happening:**

* Total attributed revenue across channels \> verified revenue.  
* The same product launch spikes “performance” on multiple platforms at once.

---

### **Mechanism 2 — Attribution windows (time rules that rewrite causality)**

An **attribution window** is a rule like: “Count a conversion if it happens within X days of an ad click (or view).”

Meta explicitly offers click-through and view-through windows (for example, a conversion may be counted if it happens within a set period after a click or a view). ([Facebook](https://www.facebook.com/business/help/460276478298895?utm_source=chatgpt.com))

Here’s the uncomfortable implication:  
If two tools use different windows—say one counts 7 days after a click, another counts 1 day after a click—they will report different realities *even if they’re both functioning perfectly.*

**Clues this is happening:**

* Discrepancy is larger on products with longer consideration cycles.  
* Campaign results “arrive late” in one system but not the other.

---

### **Mechanism 3 — View-through credit (the “I saw it, I bought later” claim)**

View-through attribution says: “The user only viewed the ad, didn’t click, but later purchased—so the ad gets credit.”

This is why platforms can report conversions that feel “too good to be true”: the user might have bought anyway. The platform is claiming influence, not necessarily causality.

**Clues this is happening:**

* Platforms show strong results even when click volume is modest.  
* Your brand is already well-known (viewing is common; clicking is optional).

(And yes—Meta’s own documentation shows that view-through is a supported part of attribution settings, meaning it can be in the numbers even when the user never clicked. ([Facebook](https://www.facebook.com/business/help/460276478298895?utm_source=chatgpt.com)))

---

### **Mechanism 4 — Signal loss and modeled conversions (the “missing tracks” problem)**

A growing share of journeys cannot be observed cleanly:

* users decline consent  
* browsers limit tracking  
* ad blockers interfere  
* cross-device identity breaks

Industry surveys show broad expectation that signal loss persists, which pushes measurement toward inference rather than direct matching. ([IAB](https://www.iab.com/wp-content/uploads/2024/03/IAB-State-of-Data-2024.pdf?utm_source=chatgpt.com))

Google explicitly describes **modeled conversions** as estimates used when conversions can’t be directly observed at the user level. ([Google Help](https://support.google.com/google-ads/answer/10081327?hl=en&utm_source=chatgpt.com))

That means: the platform can legitimately report conversions that are *not individually traceable*—because they are statistically inferred.

And it’s not a niche issue. The 2023 eyeo/Blockthrough ad-filtering research projects large-scale impact from ad blocking and documents hundreds of millions of ad-blocking users, which is exactly the kind of environment that creates measurement gaps. ([Blockthrough](https://blockthrough.com/blog/2023-pagefair-adblock-report/?utm_source=chatgpt.com))

**Clues this is happening:**

* Discrepancy grows after privacy/consent changes or tracking updates.  
* Performance appears “smoothed” in platform dashboards (less jagged than real sales).

---

### **Mechanism 5 — Revenue is messy (refunds, cancellations, taxes, shipping, and timing)**

Platforms often optimize to an event like “Purchase” or “Conversion value,” but your verified revenue may:

* subtract refunds/chargebacks  
* exclude tax/shipping  
* recognize revenue when payment clears (not when the order is placed)  
* adjust for partial refunds, exchanges, fraud filters

So the difference can be as simple as **what counts as revenue** and **when it counts**.

**Clues this is happening:**

* A spike in refunds makes verified revenue drop without platform numbers reacting.  
* Discrepancy clusters around big promo periods (when returns rise).

---

## **The emotional trap: “If numbers don’t match, I can’t trust anything.”**

That’s the wrong conclusion.

When numbers don’t match, you don’t throw them away—you treat them like instruments with **different calibration**.

A thermometer and an infrared sensor can disagree while both being useful. One measures internal temperature; the other measures surface heat. You don’t pick the “winner.” You learn what each reading *means*.

That’s what you’re doing here: translating measurement into decisions.

---

## **The 10-minute discrepancy checklist**

### **Your goal: turn “16% mismatch” into a specific diagnosis you can defend.**

You’re going to produce two outputs:

1. **Root-cause classification** (which mechanisms are driving this)  
2. **Next action** (what you change—windows, tracking, interpretation, or patience)

### **Step 1 (2 minutes): Define the two numbers precisely**

Write down:

* Platform-claimed revenue number (e.g., Meta reports $50K)  
* Verified revenue number (e.g., $42K)  
* Time range and timezone  
* Whether the platform number includes view-through credit

If you can’t define the counting rules, you can’t interpret the gap.

Meta’s attribution settings explicitly distinguish click-through and view-through counting. ([Facebook](https://www.facebook.com/business/help/460276478298895?utm_source=chatgpt.com))

---

### **Step 2 (2 minutes): Check for window mismatch**

Ask:

* What is Meta’s attribution window for this report?  
* What window is your verified reporting effectively using?

If one system counts 7 days after exposure and the other is effectively “same-day cleared payments,” a gap is expected.

---

### **Step 3 (2 minutes): Look for overlap symptoms**

Compare:

* Sum of platform-attributed revenue across channels vs verified revenue  
  If the sum exceeds verified revenue, overlap is almost certainly present.

Outcome: You can say, “We’re seeing overlapping credit assignment across platforms.”

---

### **Step 4 (2 minutes): Identify signal loss / modeling influence**

Ask:

* Did we change consent banners, tagging, pixel setup, server-side events, or tracking recently?  
* Is the platform reporting modeled conversions?

Google Ads documentation explains that modeled conversions are used when direct observation isn’t possible, and these modeled numbers can flow into reporting over time. ([Google Help](https://support.google.com/google-ads/answer/10081327?hl=en&utm_source=chatgpt.com))

If measurement is partly inferred, don’t demand perfect alignment. Demand **stability \+ directionality**.

---

### **Step 5 (2 minutes): Check revenue hygiene**

In the last period:

* did refunds spike?  
* did fraud filters tighten?  
* did shipping/tax handling change?  
* did a payment processor settlement delay occur?

If yes, your verified number moved for accounting reasons, not marketing reasons.

---

## **What to do next (decision rules)**

Use this as your default playbook:

* **If overlap is present:**  
  Don’t “fix” it by forcing one platform to match another. Instead, treat platform numbers as *channel credit*, not total truth. Move toward triangulation: verified revenue anchors reality; platforms describe distribution of influence.  
* **If window mismatch is present:**  
  Align reporting windows for comparison, or explicitly communicate: “These are different windows, so they won’t match by design.”  
* **If signal loss/modeling is the driver:**  
  Expect drift. Focus on trends, not point alignment. Verify that tagging/consent setup is stable, then watch whether the gap stabilizes.  
* **If revenue hygiene is the driver:**  
  Explain the gap in accounting terms and move on—don’t punish a channel for refunds.

---

## **The Skeptic-ready explanation** 

when someone asks, “Why doesn’t this match the platform?”

“The platform number is credited revenue based on their attribution rules (including a time window and potentially view-through credit). Our verified revenue is based on cleared transactions (system-of-record). Because platforms can double-count influence across channels and because some journeys are unobservable due to privacy/consent and are modeled, we expect a consistent gap. The important control is that verified revenue anchors total truth, while platform credit helps us understand distribution of influence. Our next step is to align windows for apples-to-apples comparison and monitor stability of the discrepancy.” ([Facebook](https://www.facebook.com/business/help/460276478298895?utm_source=chatgpt.com))

If you can say that calmly, you’re no longer defending a dashboard—you’re defending a measurement system.

---

## **Quick scenario drill (so you can pass the “week-one” test)**

**Scenario:** Platform claims **$50K** revenue. Verified revenue shows **$32K**. What happened?

A correct answer sounds like:

* “Different measurement definitions. Platform is credit; verified is cash truth.”  
* “Could be overlap across platforms, window differences, view-through credit.”  
* “Also signal loss and modeled conversions can inflate platform-reported influence.”  
* “I can diagnose which one using the checklist: windows, overlap sum, recent tracking changes, refund patterns.”

If your answering “one of them is wrong,” you’re not thinking like an operator—you’re thinking like someone trapped inside a single instrument.

---

## **Actionable takeaway**

Do this once, and you’ll never be bullied by mismatched numbers again:

1. **Name the numbers** (credit vs verified)  
2. **Classify the gap** (overlap, window, view-through, modeling, revenue hygiene)  
3. **Choose the correct response** (align, stabilize, triangulate, or ignore the noise)

Measurement doesn’t become trustworthy when it becomes perfect.  
It becomes trustworthy when you can explain it—even when it disagrees.

