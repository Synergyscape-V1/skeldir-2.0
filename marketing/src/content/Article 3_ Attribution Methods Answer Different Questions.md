# **Attribution Methods Answer Different Questions**

## **Rules, Experiments, MMM, and Bayesian Models, explained like your budget depends on it**

Most marketing arguments are not really arguments about performance. They are arguments about **the question you thought you were answering**.

You ask, “Did Meta work?”

One person answers with last click.  
Another answers with platform-reported conversions.  
Another answers with GA.  
Another answers with a model.

Everyone sounds confident. Everyone is contradicting everyone else.

And the quiet truth is this: **they are not disagreeing about the same thing.** They are answering different questions while pretending they share one.

If you learn nothing else from this piece, learn this:

**Attribution is not one tool. It is a toolbox.**  
If you pick the wrong tool, you do not get a slightly worse answer. You get a clean, confident answer to the wrong question. That is how budgets get misallocated with a straight face.

---

## **The four questions hiding underneath every attribution debate**

When someone says “attribution,” they are usually trying to answer one of these:

1. **Who touched the sale**  
   You want a clean story of the customer path. This is about credit assignment.  
2. **What caused the sale**  
   You want incrementality. You want to know what would not have happened without the ads.  
3. **Where should I allocate budget over time**  
   You want long-run allocation guidance, including diminishing returns and lagged effects.  
4. **What happens if I change spend next week**  
   You want forecasting and planning, not just explanation.

Different methods are built for different questions. Asking one method to answer all four is like asking a thermometer to tell you the future.

---

## **Method 1: Rules-based attribution**

### **What it’s good for**

Rules-based models are simple. First touch. Last click. Even splits. Position-based.

They are good for one thing: **making a consistent story quickly.**  
That can be useful for internal reporting and basic directional learning.

### **What it cannot do**

Rules-based models do not measure causality. They assign credit according to a rule. That rule can create bias.

Last click is the most common trap. It tends to over-reward whatever happens closest to purchase and under-reward what created demand earlier. WARC has published critiques linking overreliance on last-touch models to budget misallocation and even manipulative behaviors like cookie bombing. 

### **The operator takeaway**

Use rules-based attribution when you need a consistent label, not when you need the truth.

If you are making major budget shifts based on last click alone, you are not optimizing marketing. You are optimizing the rule.

---

## **Method 2: Platform-reported attribution**

### **What it’s good for**

Platform reporting is powerful for one reason: it is close to the delivery system.

It helps you optimize inside a platform because it tracks platform-native interactions and uses that platform’s own measurement logic.

### **What it cannot do**

It is siloed. It cannot see the full cross-channel story. It is also incentivized to claim credit because credit justifies spend.

This does not mean platforms are lying. It means platforms are not neutral referees.

### **The operator takeaway**

Treat platform numbers like **a channel-specific instrument**. Useful for tuning. Dangerous as a total ledger.

---

## **Method 3: Multi-touch attribution using user paths**

### **What it’s good for**

Multi-touch tries to tell a richer path story than last click. In ideal conditions, it can help you understand sequences and interactions.

### **What it cannot do**

User-level path measurement is increasingly incomplete. The modern environment includes consent choices, tracking constraints, and data loss. The IAB State of Data report shows widespread expectation that signal loss and privacy changes continue to constrain addressability and measurement. 

When paths are missing, the method can become confident about a partial movie.

### **The operator takeaway**

Multi-touch can be insightful when tracking is strong and identity resolution is stable. When tracking is weak, treat it as a partial narrative, not a courtroom transcript.

---

## **Method 4: Experiments and incrementality tests**

### **What it’s good for**

Experiments answer the question everyone secretly wants answered:

**What did the ads cause?**

Holdouts and geo tests can isolate causal lift by comparing a treated group to a control group.

### **What it cannot do**

Experiments can be slow, costly, and operationally annoying. They require discipline. They can be hard to run continuously across every channel.

### **The operator takeaway**

Use experiments when the decision is expensive and the risk of being wrong is high.

If you are about to double spend, cut spend, or declare a channel dead, an incrementality test is the closest thing to a lie detector you get.

---

## **Method 5: Marketing mix modeling**

### **What it’s good for**

MMM is built for allocation and planning.

It uses aggregated time-series data to estimate how marketing and non-marketing factors contribute to a KPI like sales. Meta’s Robyn documentation frames MMM as a holistic econometric approach used to understand budget allocation and forecast impact. 

Google’s MMM guidebook similarly positions MMM as a way to make decisions based on integrated metrics tied to business results, rather than isolated channel signals.

MMM also works in environments where user-level tracking is degraded, which is increasingly common.

### **What it cannot do**

MMM needs variation over time. If spend never changes, or if everything changes at once, separation becomes difficult. It also provides estimates at a higher level of aggregation, not a perfect user-by-user story.

### **The operator takeaway**

MMM is your budget compass. It does not tell you every footstep. It tells you which direction is north.

---

## **Method 6: Bayesian MMM and uncertainty-aware attribution**

### **What it’s good for**

Bayesian approaches do something most dashboards refuse to do.

They tell you not only an estimate, but **how uncertain that estimate is**.

Google Research has published Bayesian MMM work that estimates models using Bayesian methods and shows how to compute metrics like ROAS from posterior samples.

This matters because real decisions are not made on point estimates. They are made under uncertainty.

### **What it cannot do**

Bayesian models are not magic. With small data, priors and assumptions matter more. The model can be honest about uncertainty, but it cannot create signal out of thin air.

### **The operator takeaway**

If you are making allocation decisions, uncertainty is not a side note. It is the risk profile of the decision itself.

---

## **A practical map**

### **Which method to use, based on the decision you are making**

**If your question is “what path did users take”**  
Use multi-touch or journey views, but treat missing data as a known limitation. 

**If your question is “did this channel cause lift”**  
Use experiments and incrementality tests.

**If your question is “how should I allocate budget across channels”**  
Use MMM. Use Bayesian MMM when you want uncertainty ranges to guide risk-managed decisions. 

**If your question is “how do I optimize inside Meta or Google this week”**  
Use platform reporting as a tactical instrument, not as the total truth.

---

## **The triangulation playbook**

### **How mature teams stop arguing and start steering**

1. **Anchor on verified outcomes**  
   Revenue and orders are the ledger. Everything else is an explanation of influence.  
2. **Use platform attribution for tactical tuning**  
   Creative iteration, audience changes, bidding adjustments.  
3. **Use MMM for allocation decisions**  
   Especially when signal loss makes user-level tracking incomplete.   
4. **Use experiments to calibrate and challenge the model**  
   When the stakes are high, verify lift.  
5. **Treat uncertainty as a governance signal**  
   Wide ranges mean “reduce uncertainty before making a large move.”

This is how you defend decisions without pretending the world is simpler than it is.

---

## **Two misconceptions to kill permanently**

**Misconception one: One attribution model should match another**  
Different models answer different questions. If you force them to match, you destroy meaning.

**Misconception two: A single ROAS number is more trustworthy than a range**  
A range is often the only honest output in a world with incomplete observation. Bayesian MMM explicitly supports deriving ROAS from posterior samples, which naturally produces distributions, not a single number. 

---

## **Scenario drill**

### **Use this to test your own understanding**

1. **Your executive asks:** “Which channel drove the sale?”  
   Answer with a path view. Then immediately clarify that path is not causality.  
2. **Your CFO asks:** “Would that revenue still have happened without ads?”  
   Answer with incrementality. If you do not have an experiment, say so. Then propose one.  
3. **You ask:** “Where should I put the next $50K?”  
   Answer with MMM and uncertainty. Forecast outcomes and include risk, not just upside. 

---

## **The part nobody says out loud**

Attribution is the story you tell about money.

If your story is wrong, you will still feel confident while you burn budget.  
That is the most dangerous kind of failure. Silent. Clean. Plausible.

The goal is not to find a number that ends the debate.  
The goal is to pick the method that fits the question, then act like an adult about uncertainty.

That is how you stop being trapped in dashboards and start being trusted with budgets.

---

### **Sources for audit**

* IAB, *State of Data 2024* on ongoing signal loss and measurement constraints.   
* WARC on problems with last-click attribution and budget misallocation. Meta Robyn documentation, *An Analyst’s Guide to MMM*.   
* Google Research, *Bayesian Methods for Media Mix Modeling with Carryover and Shape Effects*.   
* Think with Google, *Marketing Mix Modeling Guidebook*. 

