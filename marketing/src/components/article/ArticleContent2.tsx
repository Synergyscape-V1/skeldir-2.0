import { Manrope } from "next/font/google";
import { ExternalLink } from "lucide-react";

const manrope = Manrope({
    subsets: ["latin"],
    weight: ["400", "500", "600", "700", "800"],
    variable: "--font-manrope",
});

// Typography styles
const styles = {
    h2: {
        fontFamily: `${manrope.style.fontFamily}, sans-serif`,
        fontSize: "clamp(28px, 4vw, 36px)",
        fontWeight: 700,
        lineHeight: 1.2,
        color: "#111827",
        marginTop: "64px",
        marginBottom: "24px",
        letterSpacing: "-0.02em",
    },
    h3: {
        fontFamily: `${manrope.style.fontFamily}, sans-serif`,
        fontSize: "clamp(20px, 3vw, 24px)",
        fontWeight: 600,
        lineHeight: 1.3,
        color: "#1F2937",
        marginTop: "48px",
        marginBottom: "16px",
    },
    p: {
        fontSize: "clamp(17px, 2vw, 18px)",
        fontWeight: 400,
        lineHeight: 1.7,
        color: "#374151",
        marginBottom: "24px",
    },
    strong: {
        fontWeight: 600,
        color: "#111827",
    },
    ul: {
        fontSize: "clamp(17px, 2vw, 18px)",
        fontWeight: 400,
        lineHeight: 1.7,
        color: "#374151",
        marginBottom: "24px",
        paddingLeft: "0",
        listStyle: "none",
    },
    li: {
        marginBottom: "12px",
        paddingLeft: "28px",
        position: "relative" as const,
    },
    hr: {
        border: "none",
        borderTop: "1px solid #E5E7EB",
        margin: "48px 0",
    },
    code: {
        fontFamily: "'Fira Code', monospace",
        backgroundColor: "#F9FAFB",
        padding: "2px 6px",
        borderRadius: "3px",
        fontSize: "0.9em",
    },
};

// External link component
function ExternalCitation({
    href,
    children,
}: {
    href: string;
    children: React.ReactNode;
}) {
    return (
        <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-blue-600 no-underline hover:underline transition-colors"
        >
            {children}
            <ExternalLink className="w-3.5 h-3.5 inline-block" />
        </a>
    );
}

// Callout box for "After reading this" section
function CalloutBox({ children }: { children: React.ReactNode }) {
    return (
        <div
            className="rounded-lg mb-8"
            style={{
                background: "linear-gradient(135deg, rgba(255, 251, 235, 0.8) 0%, rgba(239, 246, 255, 0.9) 50%, rgba(236, 254, 255, 0.85) 100%)",
                border: "1px solid rgba(147, 197, 253, 0.3)",
                padding: "24px",
                boxShadow: "0 4px 12px rgba(59, 130, 246, 0.08), 0 1px 3px rgba(0, 0, 0, 0.05), inset 0 1px 0 rgba(255, 255, 255, 0.6)",
                backdropFilter: "blur(10px)",
                WebkitBackdropFilter: "blur(10px)",
                position: "relative",
                overflow: "hidden",
            }}
        >
            {/* Subtle glossy overlay */}
            <div
                style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    right: 0,
                    height: "40%",
                    background: "linear-gradient(to bottom, rgba(255, 255, 255, 0.4), transparent)",
                    pointerEvents: "none",
                    borderRadius: "8px 8px 0 0",
                }}
            />
            <div style={{ position: "relative", zIndex: 1 }}>
                {children}
            </div>
        </div>
    );
}

// Custom bullet point
function Bullet({ color = "#3B82F6" }: { color?: string }) {
    return (
        <span
            className="absolute left-0 top-2"
            style={{
                width: "8px",
                height: "8px",
                backgroundColor: color,
                borderRadius: "50%",
            }}
        />
    );
}

// Checkmark bullet - matches ProductPage style
function CheckBullet({ gradientId = "checkGradient" }: { gradientId?: string }) {
    return (
        <svg
            width="20"
            height="20"
            viewBox="0 0 12 12"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className="absolute left-0 top-0.5"
            style={{ flexShrink: 0 }}
        >
            <defs>
                <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="100%" gradientUnits="userSpaceOnUse">
                    <stop offset="0%" stopColor="#4F46E5" />
                    <stop offset="50%" stopColor="#A855F7" />
                    <stop offset="100%" stopColor="#EC4899" />
                </linearGradient>
            </defs>
            <path
                d="M2 6L5 9L10 2"
                stroke={`url(#${gradientId})`}
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                fill="none"
            />
        </svg>
    );
}

export function ArticleContent2() {
    return (
        <div className="article-content">
            {/* Opening Hook */}
            <p style={styles.p}>
                There's a particular kind of panic that doesn't look like panic.
            </p>

            <p style={styles.p}>
                It looks like you, staring at a dashboard at 11:47 p.m., trying to
                decide whether to move money out of a channel that <em>might</em> be
                fading… or <em>might</em> be warming up… or <em>might</em> be fine
                but noisy because the world is messy and tracking is imperfect and
                your boss wants an answer in the morning.
            </p>

            <p style={styles.p}>
                A single ROAS number feels like relief.
                <br />
                A single ROAS number feels like a verdict.
                <br />
                A single ROAS number feels like the door closing.
            </p>

            <p style={styles.p}>
                And that's exactly why it's dangerous.
            </p>

            <p style={styles.p}>
                Because marketing is not a courtroom. It's weather. It's probability.
                It's systems with missing sensors. It's people moving in ways you
                can't fully see. When Skeldir shows a range—say,{" "}
                <strong style={styles.strong}>$2.80 to $3.60 ROAS</strong>—it's not
                being vague. It's doing something rarer:
            </p>

            <p style={styles.p}>
                It's telling you the truth about how much you <em>don't</em> know.
            </p>

            {/* After Reading Callout */}
            <CalloutBox>
                <p
                    style={{
                        ...styles.p,
                        marginBottom: "16px",
                        fontWeight: 600,
                        color: "#111827",
                    }}
                >
                    After reading this, you'll be able to:
                </p>
                <ul style={{ ...styles.ul, marginBottom: 0 }}>
                    <li style={styles.li}>
                        <CheckBullet gradientId="checkGradient2a" />
                        Explain what a ROAS range means (without statistics jargon).
                    </li>
                    <li style={styles.li}>
                        <CheckBullet gradientId="checkGradient2b" />
                        Tell the difference between a range that's "actionable" vs
                        "warning signs."
                    </li>
                    <li style={{ ...styles.li, marginBottom: 0 }}>
                        <CheckBullet gradientId="checkGradient2c" />
                        Choose the correct next move:{" "}
                        <strong style={styles.strong}>reallocate</strong>,{" "}
                        <strong style={styles.strong}>hold</strong>, or{" "}
                        <strong style={styles.strong}>gather more data</strong>—and
                        defend that choice.
                    </li>
                </ul>
            </CalloutBox>

            <hr style={styles.hr} />

            {/* Section: What ROAS Actually Is */}
            <h2 id="what-roas-actually-is" style={styles.h2}>
                First: what ROAS actually is
            </h2>

            <p style={styles.p}>
                <strong style={styles.strong}>ROAS (Return on Ad Spend)</strong> is
                the amount of revenue you expect per dollar spent on ads.
            </p>

            <p style={styles.p}>
                If ROAS is 3.0, you're saying:{" "}
                <em>one dollar in, three dollars out</em>—as best as you can estimate.
            </p>

            <p style={styles.p}>
                But that last part matters:{" "}
                <strong style={styles.strong}>as best as you can estimate.</strong>
            </p>

            <p style={styles.p}>
                ROAS is not a property of the universe like gravity. It's a number
                you infer from imperfect signals.
            </p>

            <hr style={styles.hr} />

            {/* Section: Why Single ROAS Is a Trap */}
            <h2 id="why-single-roas-is-a-trap" style={styles.h2}>
                Why a single ROAS number is a trap
            </h2>

            <p style={styles.p}>
                A single number pretends the world was observed perfectly.
            </p>

            <p style={styles.p}>It implies:</p>

            <ul style={{ ...styles.ul, paddingLeft: "24px" }}>
                <li style={styles.li}>
                    <Bullet />
                    we saw every customer journey,
                </li>
                <li style={styles.li}>
                    <Bullet />
                    counted conversions consistently,
                </li>
                <li style={styles.li}>
                    <Bullet />
                    separated channels cleanly,
                </li>
                <li style={styles.li}>
                    <Bullet />
                    and measured revenue without ambiguity.
                </li>
            </ul>

            <p style={styles.p}>None of that is true.</p>

            <p style={styles.p}>
                So a single ROAS point estimate isn't "precise." It's often just{" "}
                <strong style={styles.strong}>precisely formatted</strong>.
            </p>

            <p style={styles.p}>
                A range is different. A range admits: "Given the data we have, here
                are the plausible ROAS values."
            </p>

            <p style={styles.p}>
                That honesty is not a weakness. It is the only solid ground you get.
            </p>

            <hr style={styles.hr} />

            {/* Section: Confidence Range */}
            <h2 id="confidence-range-meaning" style={styles.h2}>
                What a "confidence range" actually means (and why the word matters)
            </h2>

            <p style={styles.p}>
                When Skeldir shows a ROAS range, it's typically expressing a{" "}
                <strong style={styles.strong}>credible interval</strong>—a Bayesian
                term.
            </p>

            <p style={styles.p}>
                <strong style={styles.strong}>
                    Credible interval (plain meaning):
                </strong>{" "}
                a range that contains the true value with a stated probability,
                given the model and the data.
            </p>

            <p style={styles.p}>
                Stanford's Bayesian inference notes define it this way: a 100(1−α)%
                credible interval is an interval [a,b] such that the probability
                the parameter lies in it is 1−α.
            </p>

            <p style={styles.p}>
                If the range is <em>$2.80–$3.60</em>, the core idea is:
            </p>

            <p style={styles.p}>
                "Based on the evidence we have, ROAS is most plausibly somewhere in
                here."
            </p>

            <p style={styles.p}>
                This is different from a "confidence interval" in the classical
                (frequentist) sense, which is often misunderstood even by smart
                people.
            </p>

            <hr style={styles.hr} />

            {/* Section: Where Range Comes From */}
            <h2 id="where-range-comes-from" style={styles.h2}>
                Where the range comes from (without turning your brain into a math
                classroom)
            </h2>

            <p style={styles.p}>
                Think of the model as a machine that doesn't output <em>one</em>{" "}
                answer—it outputs{" "}
                <strong style={styles.strong}>many plausible answers</strong>, each
                consistent with the data.
            </p>

            <p style={styles.p}>
                If you run the model thousands of times—each time drawing plausible
                parameter values—you get thousands of ROAS values. That cloud of
                ROAS values becomes your uncertainty picture.
            </p>

            <p style={styles.p}>
                Google's Bayesian MMM work explicitly uses this posterior-sampling
                approach and shows how to calculate ROAS and marginal ROAS from{" "}
                <strong style={styles.strong}>posterior samples</strong>.
            </p>

            <p style={styles.p}>
                So the "range" isn't decorative. It's a compressed summary of a
                whole distribution:{" "}
                <em>how the model's belief spreads across possibilities.</em>
            </p>

            <hr style={styles.hr} />

            {/* Section: Range Is a Signal */}
            <h2 id="range-is-a-signal" style={styles.h2}>
                The range is not a shrug. It's a signal.
            </h2>

            <p style={styles.p}>Most operators read ranges backwards.</p>

            <p style={styles.p}>They see:</p>

            <ul style={{ ...styles.ul, paddingLeft: "24px" }}>
                <li style={styles.li}>
                    <Bullet />
                    <strong style={styles.strong}>Narrow range</strong> → "nice, I
                    guess"
                </li>
                <li style={styles.li}>
                    <Bullet />
                    <strong style={styles.strong}>Wide range</strong> → "ugh, the
                    model is unreliable"
                </li>
            </ul>

            <p style={styles.p}>But the correct interpretation is:</p>

            <ul style={{ ...styles.ul, paddingLeft: "24px" }}>
                <li style={styles.li}>
                    <Bullet color="#10B981" />
                    <strong style={styles.strong}>Narrow range</strong> means the
                    evidence is tight enough that you can treat ROAS like a lever.
                </li>
                <li style={styles.li}>
                    <Bullet color="#10B981" />
                    <strong style={styles.strong}>Wide range</strong> means your
                    decision is operating in fog—so the best move may be to reduce
                    fog before you bet bigger.
                </li>
            </ul>

            <p style={styles.p}>That's not just "statistics." That's governance.</p>

            <hr style={styles.hr} />

            {/* Section: Why Ranges Widen */}
            <h2 id="why-ranges-widen" style={styles.h2}>
                Why ranges widen (the four causes that matter)
            </h2>

            <p style={styles.p}>
                When a ROAS range gets wide, it usually isn't because the system is
                broken. It's because the world is hard to identify.
            </p>

            {/* Cause 1 */}
            <h3 id="cause-1-sparse-data" style={styles.h3}>
                1) Sparse or unstable data
            </h3>

            <p style={styles.p}>
                Low volume weeks, sudden creative swaps, huge promos—anything that
                makes history less representative.
            </p>

            {/* Cause 2 */}
            <h3 id="cause-2-correlated-channels" style={styles.h3}>
                2) Channels that move together
            </h3>

            <p style={styles.p}>
                If multiple channels rise and fall at the same time, the model
                struggles to separate who did what. You don't get clean attribution;
                you get shared credit and uncertainty.
            </p>

            {/* Cause 3 */}
            <h3 id="cause-3-delayed-effects" style={styles.h3}>
                3) Delayed and diminishing effects
            </h3>

            <p style={styles.p}>
                Marketing often has lag (effects arrive later) and saturation
                (returns diminish). This is why MMM exists in the first place, and
                why modern approaches model carryover and non-linear response.
            </p>

            {/* Cause 4 */}
            <h3 id="cause-4-measurement-loss" style={styles.h3}>
                4) Measurement loss (you didn't see what happened)
            </h3>

            <p style={styles.p}>
                When observation gets worse, uncertainty grows. That's not
                philosophical—it's mechanical.
            </p>

            <hr style={styles.hr} />

            {/* Section: What To Do With A Range */}
            <h2 id="what-to-do-with-range" style={styles.h2}>
                What to do with a range: three action rules you can actually use
            </h2>

            <p style={styles.p}>
                You don't need a statistics degree. You need{" "}
                <strong style={styles.strong}>decision discipline</strong>.
            </p>

            {/* Rule 1 */}
            <h3 id="rule-1-worst-case" style={styles.h3}>
                Rule 1 — Act on the <em>worst-case</em> when the downside matters
            </h3>

            <p style={styles.p}>
                If your range is <strong style={styles.strong}>$2.80–$3.60</strong>,
                ask:
            </p>

            <ul style={{ ...styles.ul, paddingLeft: "24px" }}>
                <li style={styles.li}>
                    <Bullet />
                    "If it's really $2.80, is this channel still worth it?"
                </li>
            </ul>

            <p style={styles.p}>
                If yes, you can proceed. If no, you treat the move as risky until
                you narrow uncertainty.
            </p>

            <p style={styles.p}>
                This is not pessimism. It's{" "}
                <strong style={styles.strong}>risk management</strong>: you don't
                size a bet based on the best-case.
            </p>

            {/* Rule 2 */}
            <h3 id="rule-2-reallocate-confidently" style={styles.h3}>
                Rule 2 — Reallocate confidently only when the range is tight enough
                to <em>change your ranking</em>
            </h3>

            <p style={styles.p}>
                A narrow interval is powerful because it can preserve ordering.
            </p>

            <p style={styles.p}>
                If Channel A is{" "}
                <strong style={styles.strong}>$3.20–$3.40</strong> and Channel B is{" "}
                <strong style={styles.strong}>$2.10–$2.40</strong>, you don't need
                perfect precision to know A beats B.
            </p>

            <p style={styles.p}>
                But if Channel A is{" "}
                <strong style={styles.strong}>$2.00–$4.10</strong> and Channel B is{" "}
                <strong style={styles.strong}>$2.30–$3.20</strong>, the overlap
                means your ranking can flip depending on which plausible world
                you're in.
            </p>

            <p style={styles.p}>
                In overlap situations, "move budget aggressively" is often just
                gambling with nicer fonts.
            </p>

            {/* Rule 3 */}
            <h3 id="rule-3-information-gain" style={styles.h3}>
                Rule 3 — When uncertainty is wide, spend effort on{" "}
                <em>information gain</em>, not optimization
            </h3>

            <p style={styles.p}>A wide interval is your cue to ask:</p>

            <ul style={{ ...styles.ul, paddingLeft: "24px" }}>
                <li style={styles.li}>
                    <Bullet />
                    What would reduce uncertainty fastest?
                </li>
            </ul>

            <p style={styles.p}>
                Sometimes the answer is better tracking hygiene. Sometimes it's
                longer time windows. Sometimes it's running a holdout or geo test.
                Sometimes it's simply waiting for more data.
            </p>

            <p style={styles.p}>
                But the principle is the same:{" "}
                <strong style={styles.strong}>
                    don't optimize in a storm. Stabilize first.
                </strong>
            </p>

            <hr style={styles.hr} />

            {/* Section: Range-to-Action Playbook */}
            <h2 id="range-to-action-playbook" style={styles.h2}>
                The "Range-to-Action" playbook
            </h2>

            <p style={styles.p}>
                If you remember nothing else, remember this:
            </p>

            <ul style={{ ...styles.ul, paddingLeft: "24px" }}>
                <li style={styles.li}>
                    <Bullet color="#10B981" />
                    <strong style={styles.strong}>Tight range + high ROAS</strong> →{" "}
                    <strong style={styles.strong}>Scale</strong> (increase spend
                    carefully but confidently)
                </li>
                <li style={styles.li}>
                    <Bullet color="#F59E0B" />
                    <strong style={styles.strong}>Tight range + low ROAS</strong> →{" "}
                    <strong style={styles.strong}>Cut or rework</strong>{" "}
                    (creative/offer/targeting)
                </li>
                <li style={styles.li}>
                    <Bullet color="#EF4444" />
                    <strong style={styles.strong}>Wide range</strong> →{" "}
                    <strong style={styles.strong}>
                        Diagnose and reduce uncertainty
                    </strong>{" "}
                    before major shifts
                </li>
            </ul>

            <p style={styles.p}>That's it. Three moves. No mysticism.</p>

            <hr style={styles.hr} />

            {/* Section: Questions When Range Is Wide */}
            <h2 id="questions-when-range-wide" style={styles.h2}>
                What questions to ask when the range is wide
            </h2>

            <p style={styles.p}>
                Wide ranges happen. Your job is to stop treating them as insults and
                start treating them as instructions.
            </p>

            <p style={styles.p}>Ask these, in order:</p>

            <ol
                style={{
                    ...styles.ul,
                    paddingLeft: "24px",
                    listStyle: "none",
                }}
            >
                <li
                    style={{
                        ...styles.li,
                        paddingLeft: "32px",
                    }}
                >
                    <span
                        className="absolute left-0 top-0 w-6 h-6 rounded-full flex items-center justify-center text-sm font-semibold"
                        style={{ backgroundColor: "#3B82F6", color: "white" }}
                    >
                        1
                    </span>
                    <strong style={styles.strong}>
                        Is the range wide because volume is low?
                    </strong>
                    <br />
                    If yes: don't pretend the model can do miracles. You need more
                    signal.
                </li>
                <li
                    style={{
                        ...styles.li,
                        paddingLeft: "32px",
                    }}
                >
                    <span
                        className="absolute left-0 top-0 w-6 h-6 rounded-full flex items-center justify-center text-sm font-semibold"
                        style={{ backgroundColor: "#3B82F6", color: "white" }}
                    >
                        2
                    </span>
                    <strong style={styles.strong}>
                        Are channels correlated (moving together)?
                    </strong>
                    <br />
                    If yes: you need separation—different creatives, staggered tests,
                    or more variation over time.
                </li>
                <li
                    style={{
                        ...styles.li,
                        paddingLeft: "32px",
                    }}
                >
                    <span
                        className="absolute left-0 top-0 w-6 h-6 rounded-full flex items-center justify-center text-sm font-semibold"
                        style={{ backgroundColor: "#3B82F6", color: "white" }}
                    >
                        3
                    </span>
                    <strong style={styles.strong}>
                        Did something structurally change recently?
                    </strong>{" "}
                    (offer, pricing, landing page, attribution settings)
                    <br />
                    If yes: old data is less relevant. The model is telling you
                    "regime change."
                </li>
                <li
                    style={{
                        ...styles.li,
                        paddingLeft: "32px",
                        marginBottom: 0,
                    }}
                >
                    <span
                        className="absolute left-0 top-0 w-6 h-6 rounded-full flex items-center justify-center text-sm font-semibold"
                        style={{ backgroundColor: "#3B82F6", color: "white" }}
                    >
                        4
                    </span>
                    <strong style={styles.strong}>
                        Is the goal short-term optimization or long-term allocation?
                    </strong>
                    <br />
                    Short-term: uncertainty kills you.
                    <br />
                    Long-term: ranges are manageable if trends are stable.
                </li>
            </ol>

            <hr style={styles.hr} />

            {/* Section: Warning About Uncertainty Theatre */}
            <h2 id="uncertainty-theatre-warning" style={styles.h2}>
                A warning about "uncertainty theatre"
            </h2>

            <p style={styles.p}>
                There's a subtle failure mode where people treat ranges as if they
                capture <em>all</em> uncertainty.
            </p>

            <p style={styles.p}>
                They don't. They capture uncertainty{" "}
                <strong style={styles.strong}>
                    under the model's assumptions
                </strong>
                , using the data provided.
            </p>

            <p style={styles.p}>
                Statistical educators have argued for calling them "uncertainty
                intervals" precisely because people over-interpret them as total
                truth. The wider the interval, the more uncertainty—but it still
                might omit unknown unknowns.
            </p>

            <p style={styles.p}>So the mature stance is:</p>

            <ul style={{ ...styles.ul, paddingLeft: "24px" }}>
                <li style={styles.li}>
                    <Bullet />
                    Use the range as your best available honesty,
                </li>
                <li style={styles.li}>
                    <Bullet />
                    while still respecting that reality can be wilder than your model.
                </li>
            </ul>

            <p style={styles.p}>That's not a critique. That's adulthood.</p>

            <hr style={styles.hr} />

            {/* Section: Scenario Drill */}
            <h2 id="scenario-drill" style={styles.h2}>
                Scenario drill
            </h2>

            <div
                className="rounded-lg"
                style={{
                    background: "linear-gradient(135deg, rgba(255, 251, 235, 0.8) 0%, rgba(239, 246, 255, 0.9) 50%, rgba(236, 254, 255, 0.85) 100%)",
                    border: "1px solid rgba(147, 197, 253, 0.3)",
                    padding: "24px",
                    marginBottom: "24px",
                    boxShadow: "0 4px 12px rgba(59, 130, 246, 0.08), 0 1px 3px rgba(0, 0, 0, 0.05), inset 0 1px 0 rgba(255, 255, 255, 0.6)",
                    backdropFilter: "blur(10px)",
                    WebkitBackdropFilter: "blur(10px)",
                    position: "relative",
                    overflow: "hidden",
                }}
            >
                {/* Subtle glossy overlay */}
                <div
                    style={{
                        position: "absolute",
                        top: 0,
                        left: 0,
                        right: 0,
                        height: "40%",
                        background: "linear-gradient(to bottom, rgba(255, 255, 255, 0.4), transparent)",
                        pointerEvents: "none",
                        borderRadius: "8px 8px 0 0",
                    }}
                />
                <div style={{ position: "relative", zIndex: 1 }}>
                    <p
                        style={{
                            ...styles.p,
                            fontWeight: 600,
                            color: "rgba(0, 0, 0, 1)",
                            marginBottom: "8px",
                        }}
                    >
                        Scenario:
                    </p>
                    <p style={{ ...styles.p, marginBottom: 0, color: "rgba(0, 0, 0, 1)" }}>
                        Skeldir shows Facebook ROAS range{" "}
                        <strong>$2.80–$3.60</strong>. What should you do?
                    </p>
                </div>
            </div>

            <p style={styles.p}>A correct answer sounds like this:</p>

            <ol
                style={{
                    ...styles.ul,
                    paddingLeft: "24px",
                    listStyle: "none",
                }}
            >
                <li
                    style={{
                        ...styles.li,
                        paddingLeft: "32px",
                    }}
                >
                    <span
                        className="absolute left-0 top-0 w-6 h-6 rounded-full flex items-center justify-center text-sm font-semibold"
                        style={{ backgroundColor: "#111827", color: "white" }}
                    >
                        1
                    </span>
                    <strong style={styles.strong}>Interpretation:</strong>
                    <br />
                    "ROAS is plausibly between $2.80 and $3.60. That means we have
                    uncertainty; the channel's true performance could be closer to
                    either bound."
                </li>
                <li
                    style={{
                        ...styles.li,
                        paddingLeft: "32px",
                    }}
                >
                    <span
                        className="absolute left-0 top-0 w-6 h-6 rounded-full flex items-center justify-center text-sm font-semibold"
                        style={{ backgroundColor: "#111827", color: "white" }}
                    >
                        2
                    </span>
                    <strong style={styles.strong}>Decision logic:</strong>
                    <br />
                    "If $2.80 is still profitable and competitive, we can scale
                    carefully. If $2.80 would make this a worse use of dollars than
                    alternatives, we hold off on a big reallocation."
                </li>
                <li
                    style={{
                        ...styles.li,
                        paddingLeft: "32px",
                        marginBottom: 0,
                    }}
                >
                    <span
                        className="absolute left-0 top-0 w-6 h-6 rounded-full flex items-center justify-center text-sm font-semibold"
                        style={{ backgroundColor: "#111827", color: "white" }}
                    >
                        3
                    </span>
                    <strong style={styles.strong}>Next action:</strong>
                    <br />
                    "If the range is wide or overlaps with other channels' ranges, we
                    prioritize reducing uncertainty—more data, improved measurement
                    stability, or tests—before shifting budget aggressively."
                </li>
            </ol>

            <p style={styles.p}>
                That's the muscle you're building:{" "}
                <strong style={styles.strong}>
                    not "what does the number say," but "what does the uncertainty
                    allow me to do."
                </strong>
            </p>

            <hr style={styles.hr} />

            {/* Section: The Truth Underneath */}
            <h2 id="truth-underneath" style={styles.h2}>
                The truth underneath all of this
            </h2>

            <p style={styles.p}>
                Marketing teams often live inside a quiet humiliation: being asked
                to speak with certainty about a world that refuses to be certain.
            </p>

            <p style={styles.p}>
                A ROAS range is not the system failing you.
                <br />
                It is the system refusing to lie to you.
            </p>

            <p style={styles.p}>
                It's telling you:
                <br />
                "I won't hand you a fake precision and call it confidence. I will
                show you the fog—so you can decide whether to move anyway."
            </p>

            <p style={styles.p}>
                And if you learn to act on that fog—calmly, defensibly—you become
                something rare:
            </p>

            <p style={styles.p}>
                Not someone who runs campaigns.
                <br />
                Someone who can{" "}
                <strong style={styles.strong}>
                    steer money through uncertainty
                </strong>{" "}
                without pretending the uncertainty isn't there.
            </p>

            {/* Final Callout */}
            <div
                className="rounded-lg mt-12"
                style={{
                    background: "linear-gradient(135deg, rgba(255, 251, 235, 0.8) 0%, rgba(239, 246, 255, 0.9) 50%, rgba(236, 254, 255, 0.85) 100%)",
                    border: "1px solid rgba(147, 197, 253, 0.3)",
                    padding: "32px",
                    boxShadow: "0 4px 12px rgba(59, 130, 246, 0.08), 0 1px 3px rgba(0, 0, 0, 0.05), inset 0 1px 0 rgba(255, 255, 255, 0.6)",
                    backdropFilter: "blur(10px)",
                    WebkitBackdropFilter: "blur(10px)",
                    position: "relative",
                    overflow: "hidden",
                }}
            >
                {/* Subtle glossy overlay */}
                <div
                    style={{
                        position: "absolute",
                        top: 0,
                        left: 0,
                        right: 0,
                        height: "40%",
                        background: "linear-gradient(to bottom, rgba(255, 255, 255, 0.4), transparent)",
                        pointerEvents: "none",
                        borderRadius: "8px 8px 0 0",
                    }}
                />
                <div style={{ position: "relative", zIndex: 1 }}>
                    <p
                        style={{
                            fontSize: "clamp(18px, 2.5vw, 20px)",
                            fontWeight: 500,
                            lineHeight: 1.6,
                            color: "#111827",
                            marginBottom: 0,
                        }}
                    >
                        A ROAS range is not the system failing you.
                        <br />
                        <span style={{ color: "#2563EB" }}>
                            It is the system refusing to lie to you.
                        </span>
                    </p>
                </div>
            </div>
        </div>
    );
}
