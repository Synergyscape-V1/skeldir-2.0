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

// Clues/hints box
function CluesBox({ children }: { children: React.ReactNode }) {
    return (
        <div
            className="rounded-lg mb-6"
            style={{
                background: "linear-gradient(135deg, rgba(255, 251, 235, 0.8) 0%, rgba(239, 246, 255, 0.9) 50%, rgba(236, 254, 255, 0.85) 100%)",
                border: "1px solid rgba(147, 197, 253, 0.3)",
                padding: "20px 24px",
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

export function ArticleContent() {
    return (
        <div className="article-content">
            {/* Opening Hook */}
            <p style={styles.p}>
                You open Skeldir and see it:{" "}
                <strong style={styles.strong}>
                    Meta Ads revenue is 16% lower than what Meta claims.
                </strong>
                <br />
                Not 2%. Not "rounding."{" "}
                <strong style={styles.strong}>Sixteen.</strong> Enough to change
                which channel gets funded next week.
            </p>

            <p style={styles.p}>
                In that moment, your job quietly shifts. You're no longer just
                "running campaigns." You're standing between two competing stories
                about reality—one told by an ad platform, one told by the money.
            </p>

            <p style={styles.p}>
                This guide gives you a mental model that turns that uneasy gap into
                something you can{" "}
                <strong style={styles.strong}>name, explain, and act on</strong>
                —without calling support.
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
                        <CheckBullet gradientId="checkGradient1" />
                        Explain why the mismatch happens (in plain language).
                    </li>
                    <li style={styles.li}>
                        <CheckBullet gradientId="checkGradient2" />
                        Sort it into the <em>few</em> root causes that actually matter.
                    </li>
                    <li style={{ ...styles.li, marginBottom: 0 }}>
                        <CheckBullet gradientId="checkGradient3" />
                        Run a 10-minute checklist and produce a CFO-ready explanation.
                    </li>
                </ul>
            </CalloutBox>

            <hr style={styles.hr} />

            {/* Section 1: The First Rule */}
            <h2 id="the-first-rule" style={styles.h2}>
                The first rule: you are not looking at one truth—you're looking at
                two truths
            </h2>

            <p style={styles.p}>
                When Meta says "$50K revenue," it's not claiming{" "}
                <strong style={styles.strong}>cash-in-bank</strong>. It's claiming{" "}
                <strong style={styles.strong}>credit</strong>: "We believe your ads
                caused this much revenue, using our rules."
            </p>

            <p style={styles.p}>
                When Skeldir shows "$42K verified," it's anchoring to a{" "}
                <strong style={styles.strong}>system-of-record</strong>: payments and
                orders that actually cleared (think Stripe/processor truth). That is
                not "marketing influence." That's{" "}
                <strong style={styles.strong}>accounting reality</strong>.
            </p>

            <p style={styles.p}>
                So a discrepancy is not automatically a defect. It's often the{" "}
                <em>shadow</em> cast by two systems measuring two different things,
                with two different rules, from two different vantage points.
            </p>

            <p style={styles.p}>
                The ad industry has been forced into this split reality because
                measurement is increasingly constrained by privacy, consent choices,
                and signal loss—meaning platforms and tools lean more on modeling and
                inference rather than direct observation. (
                <ExternalCitation href="https://www.iab.com/wp-content/uploads/2024/03/IAB-State-of-Data-2024.pdf">
                    IAB
                </ExternalCitation>
                )
            </p>

            <hr style={styles.hr} />

            {/* Section 2: Five Mechanisms */}
            <h2 id="five-mechanisms" style={styles.h2}>
                Discrepancy isn't random. It usually comes from one (or more) of
                these five mechanisms.
            </h2>

            <p style={styles.p}>
                If you can classify the mismatch, you can stop arguing with the
                dashboard and start making decisions again.
            </p>

            {/* Mechanism 1 */}
            <h3 id="mechanism-1-double-counting" style={styles.h3}>
                Mechanism 1 — Double counting across platforms (the "two platforms,
                one sale" problem)
            </h3>

            <p style={styles.p}>
                A single customer sees a Meta ad, later clicks a Google ad, then
                buys.
            </p>

            <p style={styles.p}>
                Meta wants credit. Google wants credit. Sometimes GA4 wants credit
                too.
            </p>

            <p style={styles.p}>
                Each system is not lying; each is measuring "influence" from its own
                universe. But when you sum those credits, you can exceed the real
                revenue. That excess doesn't mean you invented money—it means you
                invented{" "}
                <strong style={styles.strong}>overlapping explanations</strong>.
            </p>

            <CluesBox>
                <p
                    style={{
                        ...styles.p,
                        fontStyle: "italic",
                        marginBottom: "12px",
                        color: "#6B7280",
                    }}
                >
                    Clues this is happening:
                </p>
                <ul style={{ ...styles.ul, marginBottom: 0, paddingLeft: "24px" }}>
                    <li style={styles.li}>
                        <Bullet />
                        Total attributed revenue across channels {">"} verified revenue.
                    </li>
                    <li style={{ ...styles.li, marginBottom: 0 }}>
                        <Bullet />
                        The same product launch spikes "performance" on multiple
                        platforms at once.
                    </li>
                </ul>
            </CluesBox>

            <hr style={styles.hr} />

            {/* Mechanism 2 */}
            <h3 id="mechanism-2-attribution-windows" style={styles.h3}>
                Mechanism 2 — Attribution windows (time rules that rewrite causality)
            </h3>

            <p style={styles.p}>
                An <strong style={styles.strong}>attribution window</strong> is a
                rule like: "Count a conversion if it happens within X days of an ad
                click (or view)."
            </p>

            <p style={styles.p}>
                Meta explicitly offers click-through and view-through windows (for
                example, a conversion may be counted if it happens within a set
                period after a click or a view). (
                <ExternalCitation href="https://www.facebook.com/business/help/460276478298895">
                    Facebook
                </ExternalCitation>
                )
            </p>

            <p style={styles.p}>
                Here's the uncomfortable implication:
                <br />
                If two tools use different windows—say one counts 7 days after a
                click, another counts 1 day after a click—they will report different
                realities{" "}
                <em>even if they're both functioning perfectly.</em>
            </p>

            <CluesBox>
                <p
                    style={{
                        ...styles.p,
                        fontStyle: "italic",
                        marginBottom: "12px",
                        color: "#6B7280",
                    }}
                >
                    Clues this is happening:
                </p>
                <ul style={{ ...styles.ul, marginBottom: 0, paddingLeft: "24px" }}>
                    <li style={styles.li}>
                        <Bullet />
                        Discrepancy is larger on products with longer consideration
                        cycles.
                    </li>
                    <li style={{ ...styles.li, marginBottom: 0 }}>
                        <Bullet />
                        Campaign results "arrive late" in one system but not the other.
                    </li>
                </ul>
            </CluesBox>

            <hr style={styles.hr} />

            {/* Mechanism 3 */}
            <h3 id="mechanism-3-view-through-credit" style={styles.h3}>
                Mechanism 3 — View-through credit (the "I saw it, I bought later"
                claim)
            </h3>

            <p style={styles.p}>
                View-through attribution says: "The user only viewed the ad, didn't
                click, but later purchased—so the ad gets credit."
            </p>

            <p style={styles.p}>
                This is why platforms can report conversions that feel "too good to
                be true": the user might have bought anyway. The platform is claiming
                influence, not necessarily causality.
            </p>

            <CluesBox>
                <p
                    style={{
                        ...styles.p,
                        fontStyle: "italic",
                        marginBottom: "12px",
                        color: "#6B7280",
                    }}
                >
                    Clues this is happening:
                </p>
                <ul style={{ ...styles.ul, marginBottom: 0, paddingLeft: "24px" }}>
                    <li style={styles.li}>
                        <Bullet />
                        Platforms show strong results even when click volume is modest.
                    </li>
                    <li style={{ ...styles.li, marginBottom: 0 }}>
                        <Bullet />
                        Your brand is already well-known (viewing is common; clicking is
                        optional).
                    </li>
                </ul>
            </CluesBox>

            <p style={styles.p}>
                (And yes—Meta's own documentation shows that view-through is a
                supported part of attribution settings, meaning it can be in the
                numbers even when the user never clicked. (
                <ExternalCitation href="https://www.facebook.com/business/help/460276478298895">
                    Facebook
                </ExternalCitation>
                ))
            </p>

            <hr style={styles.hr} />

            {/* Mechanism 4 */}
            <h3 id="mechanism-4-signal-loss" style={styles.h3}>
                Mechanism 4 — Signal loss and modeled conversions (the "missing
                tracks" problem)
            </h3>

            <p style={styles.p}>
                A growing share of journeys cannot be observed cleanly:
            </p>

            <ul style={{ ...styles.ul, paddingLeft: "24px" }}>
                <li style={styles.li}>
                    <Bullet />
                    users decline consent
                </li>
                <li style={styles.li}>
                    <Bullet />
                    browsers limit tracking
                </li>
                <li style={styles.li}>
                    <Bullet />
                    ad blockers interfere
                </li>
                <li style={styles.li}>
                    <Bullet />
                    cross-device identity breaks
                </li>
            </ul>

            <p style={styles.p}>
                Industry surveys show broad expectation that signal loss persists,
                which pushes measurement toward inference rather than direct
                matching. (
                <ExternalCitation href="https://www.iab.com/wp-content/uploads/2024/03/IAB-State-of-Data-2024.pdf">
                    IAB
                </ExternalCitation>
                )
            </p>

            <p style={styles.p}>
                Google explicitly describes{" "}
                <strong style={styles.strong}>modeled conversions</strong> as
                estimates used when conversions can't be directly observed at the
                user level. (
                <ExternalCitation href="https://support.google.com/google-ads/answer/10081327">
                    Google Help
                </ExternalCitation>
                )
            </p>

            <p style={styles.p}>
                That means: the platform can legitimately report conversions that are{" "}
                <em>not individually traceable</em>—because they are statistically
                inferred.
            </p>

            <p style={styles.p}>
                And it's not a niche issue. The 2023 eyeo/Blockthrough ad-filtering
                research projects large-scale impact from ad blocking and documents
                hundreds of millions of ad-blocking users, which is exactly the kind
                of environment that creates measurement gaps. (
                <ExternalCitation href="https://blockthrough.com/blog/2023-pagefair-adblock-report/">
                    Blockthrough
                </ExternalCitation>
                )
            </p>

            <CluesBox>
                <p
                    style={{
                        ...styles.p,
                        fontStyle: "italic",
                        marginBottom: "12px",
                        color: "#6B7280",
                    }}
                >
                    Clues this is happening:
                </p>
                <ul style={{ ...styles.ul, marginBottom: 0, paddingLeft: "24px" }}>
                    <li style={styles.li}>
                        <Bullet />
                        Discrepancy grows after privacy/consent changes or tracking
                        updates.
                    </li>
                    <li style={{ ...styles.li, marginBottom: 0 }}>
                        <Bullet />
                        Performance appears "smoothed" in platform dashboards (less
                        jagged than real sales).
                    </li>
                </ul>
            </CluesBox>

            <hr style={styles.hr} />

            {/* Mechanism 5 */}
            <h3 id="mechanism-5-revenue-messiness" style={styles.h3}>
                Mechanism 5 — Revenue is messy (refunds, cancellations, taxes,
                shipping, and timing)
            </h3>

            <p style={styles.p}>
                Platforms often optimize to an event like "Purchase" or "Conversion
                value," but your verified revenue may:
            </p>

            <ul style={{ ...styles.ul, paddingLeft: "24px" }}>
                <li style={styles.li}>
                    <Bullet />
                    subtract refunds/chargebacks
                </li>
                <li style={styles.li}>
                    <Bullet />
                    exclude tax/shipping
                </li>
                <li style={styles.li}>
                    <Bullet />
                    recognize revenue when payment clears (not when the order is placed)
                </li>
                <li style={styles.li}>
                    <Bullet />
                    adjust for partial refunds, exchanges, fraud filters
                </li>
            </ul>

            <p style={styles.p}>
                So the difference can be as simple as{" "}
                <strong style={styles.strong}>what counts as revenue</strong> and{" "}
                <strong style={styles.strong}>when it counts</strong>.
            </p>

            <CluesBox>
                <p
                    style={{
                        ...styles.p,
                        fontStyle: "italic",
                        marginBottom: "12px",
                        color: "#6B7280",
                    }}
                >
                    Clues this is happening:
                </p>
                <ul style={{ ...styles.ul, marginBottom: 0, paddingLeft: "24px" }}>
                    <li style={styles.li}>
                        <Bullet />
                        A spike in refunds makes verified revenue drop without platform
                        numbers reacting.
                    </li>
                    <li style={{ ...styles.li, marginBottom: 0 }}>
                        <Bullet />
                        Discrepancy clusters around big promo periods (when returns
                        rise).
                    </li>
                </ul>
            </CluesBox>

            <hr style={styles.hr} />

            {/* The Emotional Trap */}
            <h2 id="the-emotional-trap" style={styles.h2}>
                The emotional trap: "If numbers don't match, I can't trust anything."
            </h2>

            <p style={styles.p}>That's the wrong conclusion.</p>

            <p style={styles.p}>
                When numbers don't match, you don't throw them away—you treat them
                like instruments with{" "}
                <strong style={styles.strong}>different calibration</strong>.
            </p>

            <p style={styles.p}>
                A thermometer and an infrared sensor can disagree while both being
                useful. One measures internal temperature; the other measures surface
                heat. You don't pick the "winner." You learn what each reading{" "}
                <em>means</em>.
            </p>

            <p style={styles.p}>
                That's what you're doing here: translating measurement into
                decisions.
            </p>

            <hr style={styles.hr} />

            {/* 10-Minute Checklist */}
            <h2 id="10-minute-checklist" style={styles.h2}>
                The 10-minute discrepancy checklist
            </h2>

            <h3
                style={{
                    ...styles.h3,
                    marginTop: "24px",
                    color: "#3B82F6",
                }}
            >
                Your goal: turn "16% mismatch" into a specific diagnosis you can
                defend.
            </h3>

            <p style={styles.p}>You're going to produce two outputs:</p>

            <ol
                style={{
                    ...styles.ul,
                    paddingLeft: "24px",
                    listStyle: "none",
                    counterReset: "item",
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
                    <strong style={styles.strong}>Root-cause classification</strong>{" "}
                    (which mechanisms are driving this)
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
                        2
                    </span>
                    <strong style={styles.strong}>Next action</strong> (what you
                    change—windows, tracking, interpretation, or patience)
                </li>
            </ol>

            {/* Step 1 */}
            <h3 id="step-1-define-numbers" style={styles.h3}>
                Step 1 (2 minutes): Define the two numbers precisely
            </h3>

            <p style={styles.p}>Write down:</p>

            <ul style={{ ...styles.ul, paddingLeft: "24px" }}>
                <li style={styles.li}>
                    <Bullet />
                    Platform-claimed revenue number (e.g., Meta reports $50K)
                </li>
                <li style={styles.li}>
                    <Bullet />
                    Verified revenue number (e.g., $42K)
                </li>
                <li style={styles.li}>
                    <Bullet />
                    Time range and timezone
                </li>
                <li style={styles.li}>
                    <Bullet />
                    Whether the platform number includes view-through credit
                </li>
            </ul>

            <p style={styles.p}>
                If you can't define the counting rules, you can't interpret the gap.
            </p>

            <p style={styles.p}>
                Meta's attribution settings explicitly distinguish click-through and
                view-through counting. (
                <ExternalCitation href="https://www.facebook.com/business/help/460276478298895">
                    Facebook
                </ExternalCitation>
                )
            </p>

            <hr style={styles.hr} />

            {/* Step 2 */}
            <h3 id="step-2-check-windows" style={styles.h3}>
                Step 2 (2 minutes): Check for window mismatch
            </h3>

            <p style={styles.p}>Ask:</p>

            <ul style={{ ...styles.ul, paddingLeft: "24px" }}>
                <li style={styles.li}>
                    <Bullet />
                    What is Meta's attribution window for this report?
                </li>
                <li style={styles.li}>
                    <Bullet />
                    What window is your verified reporting effectively using?
                </li>
            </ul>

            <p style={styles.p}>
                If one system counts 7 days after exposure and the other is
                effectively "same-day cleared payments," a gap is expected.
            </p>

            <hr style={styles.hr} />

            {/* Step 3 */}
            <h3 id="step-3-look-for-overlap" style={styles.h3}>
                Step 3 (2 minutes): Look for overlap symptoms
            </h3>

            <p style={styles.p}>Compare:</p>

            <ul style={{ ...styles.ul, paddingLeft: "24px" }}>
                <li style={styles.li}>
                    <Bullet />
                    Sum of platform-attributed revenue across channels vs verified
                    revenue
                    <br />
                    If the sum exceeds verified revenue, overlap is almost certainly
                    present.
                </li>
            </ul>

            <p style={styles.p}>
                Outcome: You can say, "We're seeing overlapping credit assignment
                across platforms."
            </p>

            <hr style={styles.hr} />

            {/* Step 4 */}
            <h3 id="step-4-identify-signal-loss" style={styles.h3}>
                Step 4 (2 minutes): Identify signal loss / modeling influence
            </h3>

            <p style={styles.p}>Ask:</p>

            <ul style={{ ...styles.ul, paddingLeft: "24px" }}>
                <li style={styles.li}>
                    <Bullet />
                    Did we change consent banners, tagging, pixel setup, server-side
                    events, or tracking recently?
                </li>
                <li style={styles.li}>
                    <Bullet />
                    Is the platform reporting modeled conversions?
                </li>
            </ul>

            <p style={styles.p}>
                Google Ads documentation explains that modeled conversions are used
                when direct observation isn't possible, and these modeled numbers can
                flow into reporting over time. (
                <ExternalCitation href="https://support.google.com/google-ads/answer/10081327">
                    Google Help
                </ExternalCitation>
                )
            </p>

            <p style={styles.p}>
                If measurement is partly inferred, don't demand perfect alignment.
                Demand{" "}
                <strong style={styles.strong}>stability + directionality</strong>.
            </p>

            <hr style={styles.hr} />

            {/* Step 5 */}
            <h3 id="step-5-revenue-hygiene" style={styles.h3}>
                Step 5 (2 minutes): Check revenue hygiene
            </h3>

            <p style={styles.p}>In the last period:</p>

            <ul style={{ ...styles.ul, paddingLeft: "24px" }}>
                <li style={styles.li}>
                    <Bullet />
                    did refunds spike?
                </li>
                <li style={styles.li}>
                    <Bullet />
                    did fraud filters tighten?
                </li>
                <li style={styles.li}>
                    <Bullet />
                    did shipping/tax handling change?
                </li>
                <li style={styles.li}>
                    <Bullet />
                    did a payment processor settlement delay occur?
                </li>
            </ul>

            <p style={styles.p}>
                If yes, your verified number moved for accounting reasons, not
                marketing reasons.
            </p>

            <hr style={styles.hr} />

            {/* Decision Rules */}
            <h2 id="decision-rules" style={styles.h2}>
                What to do next (decision rules)
            </h2>

            <p style={styles.p}>Use this as your default playbook:</p>

            <ul style={{ ...styles.ul, paddingLeft: "24px" }}>
                <li style={styles.li}>
                    <Bullet color="#10B981" />
                    <strong style={styles.strong}>If overlap is present:</strong>
                    <br />
                    Don't "fix" it by forcing one platform to match another. Instead,
                    treat platform numbers as <em>channel credit</em>, not total truth.
                    Move toward triangulation: verified revenue anchors reality;
                    platforms describe distribution of influence.
                </li>
                <li style={styles.li}>
                    <Bullet color="#10B981" />
                    <strong style={styles.strong}>
                        If window mismatch is present:
                    </strong>
                    <br />
                    Align reporting windows for comparison, or explicitly communicate:
                    "These are different windows, so they won't match by design."
                </li>
                <li style={styles.li}>
                    <Bullet color="#10B981" />
                    <strong style={styles.strong}>
                        If signal loss/modeling is the driver:
                    </strong>
                    <br />
                    Expect drift. Focus on trends, not point alignment. Verify that
                    tagging/consent setup is stable, then watch whether the gap
                    stabilizes.
                </li>
                <li style={styles.li}>
                    <Bullet color="#10B981" />
                    <strong style={styles.strong}>
                        If revenue hygiene is the driver:
                    </strong>
                    <br />
                    Explain the gap in accounting terms and move on—don't punish a
                    channel for refunds.
                </li>
            </ul>

            <hr style={styles.hr} />

            {/* Skeptic-Ready Explanation */}
            <h2 id="skeptic-ready-explanation" style={styles.h2}>
                The Skeptic-ready explanation
            </h2>

            <p
                style={{
                    ...styles.p,
                    fontStyle: "italic",
                    color: "#6B7280",
                }}
            >
                when someone asks, "Why doesn't this match the platform?"
            </p>

            <div
                className="rounded-lg"
                style={{
                    backgroundColor: "#F0F9FF",
                    border: "1px solid #BAE6FD",
                    padding: "24px",
                    marginBottom: "24px",
                }}
            >
                <p style={{ ...styles.p, marginBottom: 0, fontStyle: "italic" }}>
                    "The platform number is credited revenue based on their attribution
                    rules (including a time window and potentially view-through credit).
                    Our verified revenue is based on cleared transactions
                    (system-of-record). Because platforms can double-count influence
                    across channels and because some journeys are unobservable due to
                    privacy/consent and are modeled, we expect a consistent gap. The
                    important control is that verified revenue anchors total truth,
                    while platform credit helps us understand distribution of influence.
                    Our next step is to align windows for apples-to-apples comparison
                    and monitor stability of the discrepancy." (
                    <ExternalCitation href="https://www.facebook.com/business/help/460276478298895">
                        Facebook
                    </ExternalCitation>
                    )
                </p>
            </div>

            <p style={styles.p}>
                If you can say that calmly, you're no longer defending a
                dashboard—you're defending a measurement system.
            </p>

            <hr style={styles.hr} />

            {/* Scenario Drill */}
            <h2 id="scenario-drill" style={styles.h2}>
                Quick scenario drill (so you can pass the "week-one" test)
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
                    Platform claims <strong>$50K</strong> revenue. Verified revenue
                    shows <strong>$32K</strong>. What happened?
                </p>
                </div>
            </div>

            <p style={styles.p}>A correct answer sounds like:</p>

            <ul style={{ ...styles.ul, paddingLeft: "24px" }}>
                <li style={styles.li}>
                    <Bullet />
                    "Different measurement definitions. Platform is credit; verified is
                    cash truth."
                </li>
                <li style={styles.li}>
                    <Bullet />
                    "Could be overlap across platforms, window differences, view-through
                    credit."
                </li>
                <li style={styles.li}>
                    <Bullet />
                    "Also signal loss and modeled conversions can inflate
                    platform-reported influence."
                </li>
                <li style={styles.li}>
                    <Bullet />
                    "I can diagnose which one using the checklist: windows, overlap sum,
                    recent tracking changes, refund patterns."
                </li>
            </ul>

            <p style={styles.p}>
                If your answering "one of them is wrong," you're not thinking like an
                operator—you're thinking like someone trapped inside a single
                instrument.
            </p>

            <hr style={styles.hr} />

            {/* Actionable Takeaway */}
            <h2 id="actionable-takeaway" style={styles.h2}>
                Actionable takeaway
            </h2>

            <p style={styles.p}>
                Do this once, and you'll never be bullied by mismatched numbers
                again:
            </p>

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
                    <strong style={styles.strong}>Name the numbers</strong> (credit vs
                    verified)
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
                    <strong style={styles.strong}>Classify the gap</strong> (overlap,
                    window, view-through, modeling, revenue hygiene)
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
                    <strong style={styles.strong}>Choose the correct response</strong>{" "}
                    (align, stabilize, triangulate, or ignore the noise)
                </li>
            </ol>

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
                        Measurement doesn't become trustworthy when it becomes perfect.
                        <br />
                        <span style={{ color: "#2563EB" }}>
                            It becomes trustworthy when you can explain it—even when it
                            disagrees.
                        </span>
                    </p>
                </div>
            </div>
        </div>
    );
}
