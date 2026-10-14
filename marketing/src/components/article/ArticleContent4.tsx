import type { CSSProperties } from "react";
import { ExternalLink } from "lucide-react";

// Typography styles matching the established pattern
const styles: Record<string, CSSProperties> = {
    h2: {
        fontFamily: "var(--font-manrope), Manrope, sans-serif",
        fontSize: "28px",
        fontWeight: 700,
        color: "#111827",
        marginTop: "48px",
        marginBottom: "20px",
        lineHeight: 1.3,
        letterSpacing: "-0.02em",
    },
    h3: {
        fontFamily: "var(--font-manrope), Manrope, sans-serif",
        fontSize: "22px",
        fontWeight: 600,
        color: "#1F2937",
        marginTop: "36px",
        marginBottom: "16px",
        lineHeight: 1.4,
    },
    p: {
        fontFamily: "var(--font-dm-sans), DM Sans, sans-serif",
        fontSize: "18px",
        fontWeight: 400,
        color: "#374151",
        lineHeight: 1.8,
        marginBottom: "24px",
    },
    lead: {
        fontFamily: "var(--font-dm-sans), DM Sans, sans-serif",
        fontSize: "20px",
        fontWeight: 400,
        color: "#4B5563",
        lineHeight: 1.8,
        marginBottom: "32px",
    },
    strong: {
        fontWeight: 600,
        color: "#111827",
    },
    blockquote: {
        fontFamily: "var(--font-dm-sans), DM Sans, sans-serif",
        fontSize: "20px",
        fontWeight: 500,
        fontStyle: "italic",
        color: "#1F2937",
        borderLeft: "4px solid #3B82F6",
        paddingLeft: "24px",
        marginTop: "32px",
        marginBottom: "32px",
        lineHeight: 1.7,
    },
    hr: {
        border: "none",
        borderTop: "1px solid #E5E7EB",
        margin: "48px 0",
    },
    ul: {
        marginBottom: "24px",
        paddingLeft: "0",
        listStyle: "none",
    },
    li: {
        fontFamily: "var(--font-dm-sans), DM Sans, sans-serif",
        fontSize: "18px",
        color: "#374151",
        lineHeight: 1.8,
        marginBottom: "12px",
        paddingLeft: "8px",
    },
};

// Callout box component with gradient background
function CalloutBox({ children }: { children: React.ReactNode }) {
    return (
        <div
            className="rounded-lg mb-8"
            style={{
                background:
                    "linear-gradient(135deg, rgba(255, 251, 235, 0.8) 0%, rgba(239, 246, 255, 0.9) 50%, rgba(236, 254, 255, 0.85) 100%)",
                border: "1px solid rgba(147, 197, 253, 0.3)",
                padding: "24px",
                boxShadow:
                    "0 4px 12px rgba(59, 130, 246, 0.08), 0 1px 3px rgba(0, 0, 0, 0.05), inset 0 1px 0 rgba(255, 255, 255, 0.6)",
                backdropFilter: "blur(10px)",
                position: "relative",
                overflow: "hidden",
            }}
        >
            <div
                style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    right: 0,
                    height: "50%",
                    background:
                        "linear-gradient(180deg, rgba(255, 255, 255, 0.4) 0%, rgba(255, 255, 255, 0) 100%)",
                    pointerEvents: "none",
                    borderRadius: "8px 8px 0 0",
                }}
            />
            <div style={{ position: "relative", zIndex: 1 }}>{children}</div>
        </div>
    );
}

// Insight box for key takeaways
function InsightBox({ children }: { children: React.ReactNode }) {
    return (
        <div
            className="rounded-lg mb-8"
            style={{
                background:
                    "linear-gradient(135deg, rgba(236, 253, 245, 0.9) 0%, rgba(240, 253, 250, 0.85) 50%, rgba(236, 254, 255, 0.9) 100%)",
                border: "1px solid rgba(52, 211, 153, 0.3)",
                padding: "24px",
                boxShadow:
                    "0 4px 12px rgba(16, 185, 129, 0.08), 0 1px 3px rgba(0, 0, 0, 0.05), inset 0 1px 0 rgba(255, 255, 255, 0.6)",
                backdropFilter: "blur(10px)",
                position: "relative",
                overflow: "hidden",
            }}
        >
            <div
                style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    right: 0,
                    height: "50%",
                    background:
                        "linear-gradient(180deg, rgba(255, 255, 255, 0.4) 0%, rgba(255, 255, 255, 0) 100%)",
                    pointerEvents: "none",
                    borderRadius: "8px 8px 0 0",
                }}
            />
            <div style={{ position: "relative", zIndex: 1 }}>{children}</div>
        </div>
    );
}

// Bullet point component
function Bullet() {
    return (
        <span
            style={{
                display: "inline-block",
                width: "6px",
                height: "6px",
                borderRadius: "50%",
                background: "linear-gradient(135deg, #3B82F6 0%, #8B5CF6 100%)",
                marginRight: "12px",
                flexShrink: 0,
                marginTop: "10px",
            }}
        />
    );
}

// Check bullet with gradient stroke
function CheckBullet({ gradientId = "checkGradient" }: { gradientId?: string }) {
    return (
        <svg
            width="20"
            height="20"
            viewBox="0 0 12 12"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            style={{
                flexShrink: 0,
                marginRight: "12px",
                marginTop: "4px",
            }}
        >
            <defs>
                <linearGradient
                    id={gradientId}
                    x1="0%"
                    y1="0%"
                    x2="100%"
                    y2="100%"
                >
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
            />
        </svg>
    );
}

// External citation link
function ExternalCitation({
    children,
    href,
}: {
    children: React.ReactNode;
    href: string;
}) {
    return (
        <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800 transition-colors"
            style={{ textDecoration: "none" }}
        >
            {children}
            <ExternalLink size={14} className="opacity-70" />
        </a>
    );
}

// Number badge for ordered items
function NumberBadge({ number }: { number: number }) {
    return (
        <span
            style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: "28px",
                height: "28px",
                borderRadius: "50%",
                background: "linear-gradient(135deg, #3B82F6 0%, #8B5CF6 100%)",
                color: "white",
                fontSize: "14px",
                fontWeight: 600,
                marginRight: "12px",
                flexShrink: 0,
            }}
        >
            {number}
        </span>
    );
}

export function ArticleContent4() {
    return (
        <div className="py-8 md:py-12">
            {/* Opening */}
            <p style={styles.lead}>
                There&apos;s a moment every growing business hits where marketing stops
                being &ldquo;creative&rdquo; and becomes &ldquo;accountable.&rdquo;
            </p>

            <p style={styles.p}>
                Not in the abstract. Not in the brand-deck way. In the cash way.
            </p>

            <p style={styles.p}>
                It happens when you ask to move budget and the air changes. Someone
                across the table is doing the mental math of risk. Maybe they run
                finance. Maybe they run operations. Maybe they are the founder. Maybe
                they are simply the person who gets blamed if payroll gets tight. Titles
                vary. The pressure is identical.
            </p>

            <p style={styles.p}>
                The question underneath the pushback is never really about ads.
            </p>

            <blockquote style={styles.blockquote}>It is about trust.</blockquote>

            <p style={styles.p}>
                And the uncomfortable truth is that marketing has earned some of that
                skepticism.{" "}
                <ExternalCitation href="https://www.gartner.com/en/newsroom/press-releases/2024-09-18-gartner-survey-finds-only-52-of-senior-marketing-leaders-can-prove-marketings-value-and-receive-credit-for-its-contribution-to-business-outcomes">
                    Gartner reported
                </ExternalCitation>{" "}
                that only about half of senior marketing leaders say they can prove
                marketing&apos;s value, and marketing leaders named finance leadership
                among the most skeptical groups.
            </p>

            <CalloutBox>
                <p style={{ ...styles.p, marginBottom: 0, color: "rgba(0, 0, 0, 1)" }}>
                    So if you want budget authority, you need something stronger than
                    &ldquo;the dashboard says so.&rdquo; You need a way to explain how your
                    numbers relate to reality, where they might be wrong, and why the
                    decision still makes sense.
                </p>
            </CalloutBox>

            <p style={styles.p}>This article is that method.</p>

            <hr style={styles.hr} />

            {/* The core mistake */}
            <h2 id="core-mistake" style={styles.h2}>
                The core mistake that makes budget discussions collapse
            </h2>

            <p style={styles.p}>
                Most budget debates fail because marketing tries to defend a number.
            </p>

            <p style={styles.p}>
                A single number invites a single attack.
                <br />
                If the number wobbles, the decision looks reckless.
                <br />
                If the number conflicts with another system, the whole story looks
                fragile.
            </p>

            <p style={styles.p}>The way out is simple to say and hard to do:</p>

            <InsightBox>
                <p
                    style={{
                        ...styles.p,
                        fontWeight: 600,
                        color: "rgba(0, 0, 0, 1)",
                        marginBottom: "8px",
                        fontSize: "20px",
                    }}
                >
                    Stop defending the number. Defend the method.
                </p>
                <p style={{ ...styles.p, marginBottom: 0, color: "rgba(0, 0, 0, 1)" }}>
                    When you do that, you move the conversation from argument to
                    governance.
                </p>
            </InsightBox>

            <hr style={styles.hr} />

            {/* Why marketing numbers feel soft */}
            <h2 id="why-numbers-feel-soft" style={styles.h2}>
                Why marketing numbers feel &ldquo;soft&rdquo; even when everyone is
                acting in good faith
            </h2>

            <p style={styles.p}>
                Modern measurement is not broken because marketers are careless. It is
                constrained because the environment is constrained.
            </p>

            <p style={styles.p}>
                Industry research has been blunt about this.{" "}
                <ExternalCitation href="https://www.iab.com/wp-content/uploads/2024/03/IAB-State-of-Data-2024.pdf">
                    The IAB&apos;s State of Data report
                </ExternalCitation>{" "}
                describes a world shaped by privacy by design and ongoing signal loss
                that changes addressability and measurement.
            </p>

            <p style={styles.p}>
                When signal is missing, systems fill gaps with inference. Different
                systems use different rules. Different rules produce different answers.
                That mismatch is not always a defect. It is often the shadow cast by
                incomplete observation.
            </p>

            <CalloutBox>
                <p style={{ ...styles.p, marginBottom: 0, color: "rgba(0, 0, 0, 1)" }}>
                    The mature move is not to pretend the shadow is not there. The mature
                    move is to manage it.
                </p>
            </CalloutBox>

            <hr style={styles.hr} />

            {/* The evidence chain */}
            <h2 id="evidence-chain" style={styles.h2}>
                The evidence chain that makes budget shifts defensible
            </h2>

            <p style={styles.p}>
                A defensible budget decision has an evidence chain. Think of it like
                scaffolding that keeps the argument standing even when someone pushes on
                it.
            </p>

            {/* Step 1 */}
            <h3 id="step-1-anchor-outcomes" style={styles.h3}>
                <span className="flex items-center gap-3">
                    <NumberBadge number={1} />
                    Anchor outcomes to something real
                </span>
            </h3>

            <p style={styles.p}>
                Start from the most concrete thing you have: verified outcomes. Paid
                orders. Cleared transactions. Invoices collected. Whatever is closest to
                money that actually happened.
            </p>

            <p style={styles.p}>This does two things immediately:</p>

            <ul style={styles.ul}>
                <li
                    style={{ ...styles.li, display: "flex", alignItems: "flex-start" }}
                >
                    <Bullet />
                    <span>
                        It stops the conversation from drifting into platform credit claims.
                    </span>
                </li>
                <li
                    style={{ ...styles.li, display: "flex", alignItems: "flex-start" }}
                >
                    <Bullet />
                    <span>
                        It gives you a stable base even when attribution shifts.
                    </span>
                </li>
            </ul>

            {/* Step 2 */}
            <h3 id="step-2-define-measurement" style={styles.h3}>
                <span className="flex items-center gap-3">
                    <NumberBadge number={2} />
                    Define what the measurement is actually claiming
                </span>
            </h3>

            <p style={styles.p}>
                Attribution is not a receipt. It is an estimate of contribution.
            </p>

            <p style={styles.p}>
                If you do not say that out loud, someone else will say it for you,
                usually with a tone that makes you smaller.
            </p>

            <p style={styles.p}>So you name it early:</p>

            <ul style={styles.ul}>
                <li
                    style={{ ...styles.li, display: "flex", alignItems: "flex-start" }}
                >
                    <Bullet />
                    <span>What the estimate is trying to measure</span>
                </li>
                <li
                    style={{ ...styles.li, display: "flex", alignItems: "flex-start" }}
                >
                    <Bullet />
                    <span>What it cannot measure</span>
                </li>
                <li
                    style={{ ...styles.li, display: "flex", alignItems: "flex-start" }}
                >
                    <Bullet />
                    <span>What assumptions shape it</span>
                </li>
            </ul>

            <p style={styles.p}>
                This is where trust starts rebuilding. Not because the system is
                perfect, but because you are not pretending it is.
            </p>

            {/* Step 3 */}
            <h3 id="step-3-uncertainty" style={styles.h3}>
                <span className="flex items-center gap-3">
                    <NumberBadge number={3} />
                    Treat uncertainty as a first-class input, not an embarrassment
                </span>
            </h3>

            <p style={styles.p}>
                People who carry risk do not fear uncertainty. They fear hidden
                uncertainty.
            </p>

            <p style={styles.p}>
                When you present performance as a range or a band of plausible outcomes,
                you are not being vague. You are being honest about the resolution of
                your instrument.
            </p>

            <InsightBox>
                <p style={{ ...styles.p, marginBottom: 0, color: "rgba(0, 0, 0, 1)" }}>
                    That honesty is the difference between a decision that can be defended
                    and a decision that collapses the first time numbers move.
                </p>
            </InsightBox>

            {/* Step 4 */}
            <h3 id="step-4-tie-action" style={styles.h3}>
                <span className="flex items-center gap-3">
                    <NumberBadge number={4} />
                    Tie the action to the uncertainty, not to the point estimate
                </span>
            </h3>

            <p style={styles.p}>
                This is where budget conversations usually turn from emotional to
                rational.
            </p>

            <p style={styles.p}>
                If uncertainty is narrow, action can be stronger.
                <br />
                If uncertainty is wide, action should be smaller and more controlled.
            </p>

            <p style={styles.p}>
                This is how disciplined teams operate in every other domain that deals
                with noisy signals. Finance leaders, for example, routinely frame
                decisions around uncertainty and risk posture.{" "}
                <ExternalCitation href="https://www.deloitte.com/us/en/programs/chief-financial-officer/articles/cfo-signals-quarterly-survey.html">
                    Deloitte&apos;s CFO Signals
                </ExternalCitation>{" "}
                is essentially a recurring snapshot of that mindset under shifting
                conditions.
            </p>

            <p style={styles.p}>
                The principle generalizes far beyond any single title:
            </p>

            <ul style={styles.ul}>
                <li
                    style={{ ...styles.li, display: "flex", alignItems: "flex-start" }}
                >
                    <CheckBullet gradientId="check1" />
                    <span>
                        <strong style={styles.strong}>Narrow uncertainty</strong> supports
                        decisive allocation.
                    </span>
                </li>
                <li
                    style={{ ...styles.li, display: "flex", alignItems: "flex-start" }}
                >
                    <CheckBullet gradientId="check2" />
                    <span>
                        <strong style={styles.strong}>Wide uncertainty</strong> demands
                        evidence-building before large reallocations.
                    </span>
                </li>
            </ul>

            {/* Step 5 */}
            <h3 id="step-5-guardrails" style={styles.h3}>
                <span className="flex items-center gap-3">
                    <NumberBadge number={5} />
                    Add guardrails so being wrong is survivable
                </span>
            </h3>

            <p style={styles.p}>
                Guardrails are not bureaucracy. Guardrails are respect for reality.
            </p>

            <p style={styles.p}>
                A budget shift becomes defensible when you can explain how you limit
                downside:
            </p>

            <ul style={styles.ul}>
                <li
                    style={{ ...styles.li, display: "flex", alignItems: "flex-start" }}
                >
                    <Bullet />
                    <span>staged reallocation rather than an all-at-once swing</span>
                </li>
                <li
                    style={{ ...styles.li, display: "flex", alignItems: "flex-start" }}
                >
                    <Bullet />
                    <span>caps on spend increases</span>
                </li>
                <li
                    style={{ ...styles.li, display: "flex", alignItems: "flex-start" }}
                >
                    <Bullet />
                    <span>thresholds that trigger a rollback</span>
                </li>
                <li
                    style={{ ...styles.li, display: "flex", alignItems: "flex-start" }}
                >
                    <Bullet />
                    <span>monitoring cadence tied to verified outcomes</span>
                </li>
            </ul>

            <CalloutBox>
                <p style={{ ...styles.p, marginBottom: 0, color: "rgba(0, 0, 0, 1)" }}>
                    Without guardrails, you are asking someone to trust you.
                    <br />
                    With guardrails, you are proving you have thought about failure.
                </p>
            </CalloutBox>

            {/* Step 6 */}
            <h3 id="step-6-validation" style={styles.h3}>
                <span className="flex items-center gap-3">
                    <NumberBadge number={6} />
                    Commit to the next validation step
                </span>
            </h3>

            <p style={styles.p}>
                The final link in the chain is learning velocity.
            </p>

            <p style={styles.p}>
                A healthy budget decision includes a plan to reduce uncertainty after
                the move:
            </p>

            <ul style={styles.ul}>
                <li
                    style={{ ...styles.li, display: "flex", alignItems: "flex-start" }}
                >
                    <Bullet />
                    <span>stabilizing measurement inputs</span>
                </li>
                <li
                    style={{ ...styles.li, display: "flex", alignItems: "flex-start" }}
                >
                    <Bullet />
                    <span>isolating changes so you can interpret results</span>
                </li>
                <li
                    style={{ ...styles.li, display: "flex", alignItems: "flex-start" }}
                >
                    <Bullet />
                    <span>running a controlled test when stakes justify it</span>
                </li>
                <li
                    style={{ ...styles.li, display: "flex", alignItems: "flex-start" }}
                >
                    <Bullet />
                    <span>
                        extending observation windows when the purchase cycle demands it
                    </span>
                </li>
            </ul>

            <p style={styles.p}>
                Even when a business is small, this matters. It prevents the common trap
                where every week becomes a new debate because nothing was designed to
                produce clearer evidence over time.
            </p>

            <hr style={styles.hr} />

            {/* Sources */}
            <h3 style={styles.h3}>Sources for audit</h3>

            <ul style={styles.ul}>
                <li
                    style={{ ...styles.li, display: "flex", alignItems: "flex-start" }}
                >
                    <Bullet />
                    <span>
                        <ExternalCitation href="https://www.gartner.com/en/newsroom/press-releases/2024-09-18-gartner-survey-finds-only-52-of-senior-marketing-leaders-can-prove-marketings-value-and-receive-credit-for-its-contribution-to-business-outcomes">
                            Gartner
                        </ExternalCitation>{" "}
                        on marketing leaders proving value and finance skepticism.
                    </span>
                </li>
                <li
                    style={{ ...styles.li, display: "flex", alignItems: "flex-start" }}
                >
                    <Bullet />
                    <span>
                        <ExternalCitation href="https://www.iab.com/wp-content/uploads/2024/03/IAB-State-of-Data-2024.pdf">
                            IAB, State of Data 2024
                        </ExternalCitation>{" "}
                        on signal loss and measurement constraints.
                    </span>
                </li>
                <li
                    style={{ ...styles.li, display: "flex", alignItems: "flex-start" }}
                >
                    <Bullet />
                    <span>
                        <ExternalCitation href="https://www.deloitte.com/us/en/programs/chief-financial-officer/articles/cfo-signals-quarterly-survey.html">
                            Deloitte CFO Signals
                        </ExternalCitation>{" "}
                        on CFO decision-making under uncertainty.
                    </span>
                </li>
            </ul>
        </div>
    );
}
