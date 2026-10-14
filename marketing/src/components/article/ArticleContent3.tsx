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
    ol: {
        marginBottom: "24px",
        paddingLeft: "24px",
        listStyleType: "decimal",
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

export function ArticleContent3() {
    return (
        <div className="py-8 md:py-12">
            {/* Opening */}
            <p style={styles.lead}>
                Most marketing arguments are not really arguments about performance.
                They are arguments about{" "}
                <strong style={styles.strong}>
                    the question you thought you were answering
                </strong>
                .
            </p>

            <p style={styles.p}>
                You ask, &ldquo;Did Meta work?&rdquo;
            </p>

            <p style={styles.p}>
                One person answers with last click.
                <br />
                Another answers with platform-reported conversions.
                <br />
                Another answers with GA.
                <br />
                Another answers with a model.
            </p>

            <p style={styles.p}>
                Everyone sounds confident. Everyone is contradicting everyone else.
            </p>

            <p style={styles.p}>
                And the quiet truth is this:{" "}
                <strong style={styles.strong}>
                    they are not disagreeing about the same thing.
                </strong>{" "}
                They are answering different questions while pretending they share one.
            </p>

            <CalloutBox>
                <p style={{ ...styles.p, marginBottom: 0, color: "rgba(0, 0, 0, 1)" }}>
                    <strong style={styles.strong}>Attribution is not one tool. It is a toolbox.</strong>
                    <br />
                    If you pick the wrong tool, you do not get a slightly worse answer.
                    You get a clean, confident answer to the wrong question. That is how
                    budgets get misallocated with a straight face.
                </p>
            </CalloutBox>

            <hr style={styles.hr} />

            {/* The four questions */}
            <h2 id="four-questions" style={styles.h2}>
                The four questions hiding underneath every attribution debate
            </h2>

            <p style={styles.p}>
                When someone says &ldquo;attribution,&rdquo; they are usually trying to
                answer one of these:
            </p>

            <div className="space-y-4 mb-8">
                <div className="flex items-start">
                    <NumberBadge number={1} />
                    <div>
                        <p style={{ ...styles.p, marginBottom: "4px" }}>
                            <strong style={styles.strong}>Who touched the sale</strong>
                        </p>
                        <p style={{ ...styles.p, marginBottom: 0, fontSize: "16px", color: "#6B7280" }}>
                            You want a clean story of the customer path. This is about credit assignment.
                        </p>
                    </div>
                </div>

                <div className="flex items-start">
                    <NumberBadge number={2} />
                    <div>
                        <p style={{ ...styles.p, marginBottom: "4px" }}>
                            <strong style={styles.strong}>What caused the sale</strong>
                        </p>
                        <p style={{ ...styles.p, marginBottom: 0, fontSize: "16px", color: "#6B7280" }}>
                            You want incrementality. You want to know what would not have happened without the ads.
                        </p>
                    </div>
                </div>

                <div className="flex items-start">
                    <NumberBadge number={3} />
                    <div>
                        <p style={{ ...styles.p, marginBottom: "4px" }}>
                            <strong style={styles.strong}>Where should I allocate budget over time</strong>
                        </p>
                        <p style={{ ...styles.p, marginBottom: 0, fontSize: "16px", color: "#6B7280" }}>
                            You want long-run allocation guidance, including diminishing returns and lagged effects.
                        </p>
                    </div>
                </div>

                <div className="flex items-start">
                    <NumberBadge number={4} />
                    <div>
                        <p style={{ ...styles.p, marginBottom: "4px" }}>
                            <strong style={styles.strong}>What happens if I change spend next week</strong>
                        </p>
                        <p style={{ ...styles.p, marginBottom: 0, fontSize: "16px", color: "#6B7280" }}>
                            You want forecasting and planning, not just explanation.
                        </p>
                    </div>
                </div>
            </div>

            <p style={styles.p}>
                Different methods are built for different questions. Asking one method
                to answer all four is like asking a thermometer to tell you the future.
            </p>

            <hr style={styles.hr} />

            {/* Method 1: Rules-based */}
            <h2 id="method-1-rules-based" style={styles.h2}>
                Method 1: Rules-based attribution
            </h2>

            <h3 id="method-1-good-for" style={styles.h3}>
                What it&apos;s good for
            </h3>

            <p style={styles.p}>
                Rules-based models are simple. First touch. Last click. Even splits.
                Position-based.
            </p>

            <p style={styles.p}>
                They are good for one thing:{" "}
                <strong style={styles.strong}>making a consistent story quickly.</strong>
                <br />
                That can be useful for internal reporting and basic directional learning.
            </p>

            <h3 id="method-1-cannot-do" style={styles.h3}>
                What it cannot do
            </h3>

            <p style={styles.p}>
                Rules-based models do not measure causality. They assign credit according
                to a rule. That rule can create bias.
            </p>

            <p style={styles.p}>
                Last click is the most common trap. It tends to over-reward whatever
                happens closest to purchase and under-reward what created demand earlier.{" "}
                <ExternalCitation href="https://www.warc.com">
                    WARC has published critiques
                </ExternalCitation>{" "}
                linking overreliance on last-touch models to budget misallocation and even
                manipulative behaviors like cookie bombing.
            </p>

            <InsightBox>
                <p
                    style={{
                        ...styles.p,
                        fontWeight: 600,
                        color: "rgba(0, 0, 0, 1)",
                        marginBottom: "8px",
                    }}
                >
                    The operator takeaway
                </p>
                <p style={{ ...styles.p, marginBottom: 0, color: "rgba(0, 0, 0, 1)" }}>
                    Use rules-based attribution when you need a consistent label, not when
                    you need the truth. If you are making major budget shifts based on last
                    click alone, you are not optimizing marketing. You are optimizing the rule.
                </p>
            </InsightBox>

            <hr style={styles.hr} />

            {/* Method 2: Platform-reported */}
            <h2 id="method-2-platform-reported" style={styles.h2}>
                Method 2: Platform-reported attribution
            </h2>

            <h3 id="method-2-good-for" style={styles.h3}>
                What it&apos;s good for
            </h3>

            <p style={styles.p}>
                Platform reporting is powerful for one reason: it is close to the
                delivery system.
            </p>

            <p style={styles.p}>
                It helps you optimize inside a platform because it tracks platform-native
                interactions and uses that platform&apos;s own measurement logic.
            </p>

            <h3 id="method-2-cannot-do" style={styles.h3}>
                What it cannot do
            </h3>

            <p style={styles.p}>
                It is siloed. It cannot see the full cross-channel story. It is also
                incentivized to claim credit because credit justifies spend.
            </p>

            <p style={styles.p}>
                This does not mean platforms are lying. It means platforms are not
                neutral referees.
            </p>

            <InsightBox>
                <p
                    style={{
                        ...styles.p,
                        fontWeight: 600,
                        color: "rgba(0, 0, 0, 1)",
                        marginBottom: "8px",
                    }}
                >
                    The operator takeaway
                </p>
                <p style={{ ...styles.p, marginBottom: 0, color: "rgba(0, 0, 0, 1)" }}>
                    Treat platform numbers like{" "}
                    <strong>a channel-specific instrument</strong>. Useful for tuning.
                    Dangerous as a total ledger.
                </p>
            </InsightBox>

            <hr style={styles.hr} />

            {/* Method 3: Multi-touch */}
            <h2 id="method-3-multi-touch" style={styles.h2}>
                Method 3: Multi-touch attribution using user paths
            </h2>

            <h3 id="method-3-good-for" style={styles.h3}>
                What it&apos;s good for
            </h3>

            <p style={styles.p}>
                Multi-touch tries to tell a richer path story than last click. In ideal
                conditions, it can help you understand sequences and interactions.
            </p>

            <h3 id="method-3-cannot-do" style={styles.h3}>
                What it cannot do
            </h3>

            <p style={styles.p}>
                User-level path measurement is increasingly incomplete. The modern
                environment includes consent choices, tracking constraints, and data loss.{" "}
                <ExternalCitation href="https://www.iab.com/insights/state-of-data-2024/">
                    The IAB State of Data report
                </ExternalCitation>{" "}
                shows widespread expectation that signal loss and privacy changes continue
                to constrain addressability and measurement.
            </p>

            <p style={styles.p}>
                When paths are missing, the method can become confident about a partial movie.
            </p>

            <InsightBox>
                <p
                    style={{
                        ...styles.p,
                        fontWeight: 600,
                        color: "rgba(0, 0, 0, 1)",
                        marginBottom: "8px",
                    }}
                >
                    The operator takeaway
                </p>
                <p style={{ ...styles.p, marginBottom: 0, color: "rgba(0, 0, 0, 1)" }}>
                    Multi-touch can be insightful when tracking is strong and identity
                    resolution is stable. When tracking is weak, treat it as a partial
                    narrative, not a courtroom transcript.
                </p>
            </InsightBox>

            <hr style={styles.hr} />

            {/* Method 4: Experiments */}
            <h2 id="method-4-experiments" style={styles.h2}>
                Method 4: Experiments and incrementality tests
            </h2>

            <h3 id="method-4-good-for" style={styles.h3}>
                What it&apos;s good for
            </h3>

            <p style={styles.p}>
                Experiments answer the question everyone secretly wants answered:
            </p>

            <blockquote style={styles.blockquote}>
                What did the ads cause?
            </blockquote>

            <p style={styles.p}>
                Holdouts and geo tests can isolate causal lift by comparing a treated
                group to a control group.
            </p>

            <h3 id="method-4-cannot-do" style={styles.h3}>
                What it cannot do
            </h3>

            <p style={styles.p}>
                Experiments can be slow, costly, and operationally annoying. They require
                discipline. They can be hard to run continuously across every channel.
            </p>

            <InsightBox>
                <p
                    style={{
                        ...styles.p,
                        fontWeight: 600,
                        color: "rgba(0, 0, 0, 1)",
                        marginBottom: "8px",
                    }}
                >
                    The operator takeaway
                </p>
                <p style={{ ...styles.p, marginBottom: 0, color: "rgba(0, 0, 0, 1)" }}>
                    Use experiments when the decision is expensive and the risk of being
                    wrong is high. If you are about to double spend, cut spend, or declare
                    a channel dead, an incrementality test is the closest thing to a lie
                    detector you get.
                </p>
            </InsightBox>

            <hr style={styles.hr} />

            {/* Method 5: MMM */}
            <h2 id="method-5-mmm" style={styles.h2}>
                Method 5: Marketing mix modeling
            </h2>

            <h3 id="method-5-good-for" style={styles.h3}>
                What it&apos;s good for
            </h3>

            <p style={styles.p}>
                MMM is built for allocation and planning.
            </p>

            <p style={styles.p}>
                It uses aggregated time-series data to estimate how marketing and
                non-marketing factors contribute to a KPI like sales.{" "}
                <ExternalCitation href="https://facebookexperimental.github.io/Robyn/">
                    Meta&apos;s Robyn documentation
                </ExternalCitation>{" "}
                frames MMM as a holistic econometric approach used to understand budget
                allocation and forecast impact.
            </p>

            <p style={styles.p}>
                <ExternalCitation href="https://www.thinkwithgoogle.com/marketing-strategies/data-and-measurement/marketing-mix-model-guide/">
                    Google&apos;s MMM guidebook
                </ExternalCitation>{" "}
                similarly positions MMM as a way to make decisions based on integrated
                metrics tied to business results, rather than isolated channel signals.
            </p>

            <p style={styles.p}>
                MMM also works in environments where user-level tracking is degraded,
                which is increasingly common.
            </p>

            <h3 id="method-5-cannot-do" style={styles.h3}>
                What it cannot do
            </h3>

            <p style={styles.p}>
                MMM needs variation over time. If spend never changes, or if everything
                changes at once, separation becomes difficult. It also provides estimates
                at a higher level of aggregation, not a perfect user-by-user story.
            </p>

            <InsightBox>
                <p
                    style={{
                        ...styles.p,
                        fontWeight: 600,
                        color: "rgba(0, 0, 0, 1)",
                        marginBottom: "8px",
                    }}
                >
                    The operator takeaway
                </p>
                <p style={{ ...styles.p, marginBottom: 0, color: "rgba(0, 0, 0, 1)" }}>
                    MMM is your budget compass. It does not tell you every footstep. It
                    tells you which direction is north.
                </p>
            </InsightBox>

            <hr style={styles.hr} />

            {/* Method 6: Bayesian MMM */}
            <h2 id="method-6-bayesian-mmm" style={styles.h2}>
                Method 6: Bayesian MMM and uncertainty-aware attribution
            </h2>

            <h3 id="method-6-good-for" style={styles.h3}>
                What it&apos;s good for
            </h3>

            <p style={styles.p}>
                Bayesian approaches do something most dashboards refuse to do.
            </p>

            <p style={styles.p}>
                They tell you not only an estimate, but{" "}
                <strong style={styles.strong}>how uncertain that estimate is</strong>.
            </p>

            <p style={styles.p}>
                <ExternalCitation href="https://research.google/pubs/pub46001/">
                    Google Research has published Bayesian MMM work
                </ExternalCitation>{" "}
                that estimates models using Bayesian methods and shows how to compute
                metrics like ROAS from posterior samples.
            </p>

            <p style={styles.p}>
                This matters because real decisions are not made on point estimates. They
                are made under uncertainty.
            </p>

            <h3 id="method-6-cannot-do" style={styles.h3}>
                What it cannot do
            </h3>

            <p style={styles.p}>
                Bayesian models are not magic. With small data, priors and assumptions
                matter more. The model can be honest about uncertainty, but it cannot
                create signal out of thin air.
            </p>

            <InsightBox>
                <p
                    style={{
                        ...styles.p,
                        fontWeight: 600,
                        color: "rgba(0, 0, 0, 1)",
                        marginBottom: "8px",
                    }}
                >
                    The operator takeaway
                </p>
                <p style={{ ...styles.p, marginBottom: 0, color: "rgba(0, 0, 0, 1)" }}>
                    If you are making allocation decisions, uncertainty is not a side note.
                    It is the risk profile of the decision itself.
                </p>
            </InsightBox>

            <hr style={styles.hr} />

            {/* Practical map */}
            <h2 id="practical-map" style={styles.h2}>
                A practical map
            </h2>

            <h3 id="which-method-to-use" style={styles.h3}>
                Which method to use, based on the decision you are making
            </h3>

            <div className="space-y-4 mb-8">
                <div className="flex items-start">
                    <Bullet />
                    <p style={{ ...styles.p, marginBottom: 0 }}>
                        <strong style={styles.strong}>
                            If your question is &ldquo;what path did users take&rdquo;
                        </strong>
                        <br />
                        Use multi-touch or journey views, but treat missing data as a known
                        limitation.
                    </p>
                </div>

                <div className="flex items-start">
                    <Bullet />
                    <p style={{ ...styles.p, marginBottom: 0 }}>
                        <strong style={styles.strong}>
                            If your question is &ldquo;did this channel cause lift&rdquo;
                        </strong>
                        <br />
                        Use experiments and incrementality tests.
                    </p>
                </div>

                <div className="flex items-start">
                    <Bullet />
                    <p style={{ ...styles.p, marginBottom: 0 }}>
                        <strong style={styles.strong}>
                            If your question is &ldquo;how should I allocate budget across
                            channels&rdquo;
                        </strong>
                        <br />
                        Use MMM. Use Bayesian MMM when you want uncertainty ranges to guide
                        risk-managed decisions.
                    </p>
                </div>

                <div className="flex items-start">
                    <Bullet />
                    <p style={{ ...styles.p, marginBottom: 0 }}>
                        <strong style={styles.strong}>
                            If your question is &ldquo;how do I optimize inside Meta or Google
                            this week&rdquo;
                        </strong>
                        <br />
                        Use platform reporting as a tactical instrument, not as the total
                        truth.
                    </p>
                </div>
            </div>

            <hr style={styles.hr} />

            {/* Triangulation playbook */}
            <h2 id="triangulation-playbook" style={styles.h2}>
                The triangulation playbook
            </h2>

            <h3 id="how-mature-teams" style={styles.h3}>
                How mature teams stop arguing and start steering
            </h3>

            <div className="space-y-4 mb-8">
                <div className="flex items-start">
                    <CheckBullet gradientId="check1" />
                    <p style={{ ...styles.p, marginBottom: 0 }}>
                        <strong style={styles.strong}>Anchor on verified outcomes</strong>
                        <br />
                        Revenue and orders are the ledger. Everything else is an explanation
                        of influence.
                    </p>
                </div>

                <div className="flex items-start">
                    <CheckBullet gradientId="check2" />
                    <p style={{ ...styles.p, marginBottom: 0 }}>
                        <strong style={styles.strong}>
                            Use platform attribution for tactical tuning
                        </strong>
                        <br />
                        Creative iteration, audience changes, bidding adjustments.
                    </p>
                </div>

                <div className="flex items-start">
                    <CheckBullet gradientId="check3" />
                    <p style={{ ...styles.p, marginBottom: 0 }}>
                        <strong style={styles.strong}>Use MMM for allocation decisions</strong>
                        <br />
                        Especially when signal loss makes user-level tracking incomplete.
                    </p>
                </div>

                <div className="flex items-start">
                    <CheckBullet gradientId="check4" />
                    <p style={{ ...styles.p, marginBottom: 0 }}>
                        <strong style={styles.strong}>
                            Use experiments to calibrate and challenge the model
                        </strong>
                        <br />
                        When the stakes are high, verify lift.
                    </p>
                </div>

                <div className="flex items-start">
                    <CheckBullet gradientId="check5" />
                    <p style={{ ...styles.p, marginBottom: 0 }}>
                        <strong style={styles.strong}>
                            Treat uncertainty as a governance signal
                        </strong>
                        <br />
                        Wide ranges mean &ldquo;reduce uncertainty before making a large
                        move.&rdquo;
                    </p>
                </div>
            </div>

            <p style={styles.p}>
                This is how you defend decisions without pretending the world is simpler
                than it is.
            </p>

            <hr style={styles.hr} />

            {/* Two misconceptions */}
            <h2 id="two-misconceptions" style={styles.h2}>
                Two misconceptions to kill permanently
            </h2>

            <CalloutBox>
                <p
                    style={{
                        ...styles.p,
                        fontWeight: 600,
                        color: "rgba(0, 0, 0, 1)",
                        marginBottom: "12px",
                    }}
                >
                    Misconception one: One attribution model should match another
                </p>
                <p style={{ ...styles.p, marginBottom: 0, color: "rgba(0, 0, 0, 1)" }}>
                    Different models answer different questions. If you force them to
                    match, you destroy meaning.
                </p>
            </CalloutBox>

            <CalloutBox>
                <p
                    style={{
                        ...styles.p,
                        fontWeight: 600,
                        color: "rgba(0, 0, 0, 1)",
                        marginBottom: "12px",
                    }}
                >
                    Misconception two: A single ROAS number is more trustworthy than a range
                </p>
                <p style={{ ...styles.p, marginBottom: 0, color: "rgba(0, 0, 0, 1)" }}>
                    A range is often the only honest output in a world with incomplete
                    observation.{" "}
                    <ExternalCitation href="https://research.google/pubs/pub46001/">
                        Bayesian MMM explicitly supports
                    </ExternalCitation>{" "}
                    deriving ROAS from posterior samples, which naturally produces
                    distributions, not a single number.
                </p>
            </CalloutBox>

            <hr style={styles.hr} />

            {/* Scenario drill */}
            <h2 id="scenario-drill" style={styles.h2}>
                Scenario drill
            </h2>

            <h3 style={styles.h3}>Use this to test your own understanding</h3>

            <div className="space-y-6 mb-8">
                <div
                    className="rounded-lg p-6"
                    style={{
                        background:
                            "linear-gradient(135deg, rgba(238, 242, 255, 0.9) 0%, rgba(245, 243, 255, 0.85) 50%, rgba(252, 231, 243, 0.9) 100%)",
                        border: "1px solid rgba(139, 92, 246, 0.2)",
                    }}
                >
                    <p style={{ ...styles.p, fontWeight: 600, marginBottom: "8px" }}>
                        1. Your executive asks: &ldquo;Which channel drove the sale?&rdquo;
                    </p>
                    <p style={{ ...styles.p, marginBottom: 0, color: "#4B5563" }}>
                        Answer with a path view. Then immediately clarify that path is not
                        causality.
                    </p>
                </div>

                <div
                    className="rounded-lg p-6"
                    style={{
                        background:
                            "linear-gradient(135deg, rgba(238, 242, 255, 0.9) 0%, rgba(245, 243, 255, 0.85) 50%, rgba(252, 231, 243, 0.9) 100%)",
                        border: "1px solid rgba(139, 92, 246, 0.2)",
                    }}
                >
                    <p style={{ ...styles.p, fontWeight: 600, marginBottom: "8px" }}>
                        2. Your CFO asks: &ldquo;Would that revenue still have happened
                        without ads?&rdquo;
                    </p>
                    <p style={{ ...styles.p, marginBottom: 0, color: "#4B5563" }}>
                        Answer with incrementality. If you do not have an experiment, say so.
                        Then propose one.
                    </p>
                </div>

                <div
                    className="rounded-lg p-6"
                    style={{
                        background:
                            "linear-gradient(135deg, rgba(238, 242, 255, 0.9) 0%, rgba(245, 243, 255, 0.85) 50%, rgba(252, 231, 243, 0.9) 100%)",
                        border: "1px solid rgba(139, 92, 246, 0.2)",
                    }}
                >
                    <p style={{ ...styles.p, fontWeight: 600, marginBottom: "8px" }}>
                        3. You ask: &ldquo;Where should I put the next $50K?&rdquo;
                    </p>
                    <p style={{ ...styles.p, marginBottom: 0, color: "#4B5563" }}>
                        Answer with MMM and uncertainty. Forecast outcomes and include risk,
                        not just upside.
                    </p>
                </div>
            </div>

            <hr style={styles.hr} />

            {/* The part nobody says */}
            <h2 id="the-truth" style={styles.h2}>
                The part nobody says out loud
            </h2>

            <p style={styles.p}>Attribution is the story you tell about money.</p>

            <p style={styles.p}>
                If your story is wrong, you will still feel confident while you burn
                budget.
                <br />
                That is the most dangerous kind of failure. Silent. Clean. Plausible.
            </p>

            <CalloutBox>
                <p style={{ ...styles.p, marginBottom: 0, color: "rgba(0, 0, 0, 1)" }}>
                    The goal is not to find a number that ends the debate.
                    <br />
                    The goal is to pick the method that fits the question, then act like an
                    adult about uncertainty.
                </p>
            </CalloutBox>

            <p style={styles.p}>
                That is how you stop being trapped in dashboards and start being trusted
                with budgets.
            </p>

            <hr style={styles.hr} />

            {/* Sources */}
            <h3 style={styles.h3}>Sources for audit</h3>

            <ul style={styles.ul}>
                <li style={{ ...styles.li, display: "flex", alignItems: "flex-start" }}>
                    <Bullet />
                    <span>
                        <ExternalCitation href="https://www.iab.com/insights/state-of-data-2024/">
                            IAB, State of Data 2024
                        </ExternalCitation>{" "}
                        on ongoing signal loss and measurement constraints.
                    </span>
                </li>
                <li style={{ ...styles.li, display: "flex", alignItems: "flex-start" }}>
                    <Bullet />
                    <span>
                        <ExternalCitation href="https://www.warc.com">
                            WARC
                        </ExternalCitation>{" "}
                        on problems with last-click attribution and budget misallocation.
                    </span>
                </li>
                <li style={{ ...styles.li, display: "flex", alignItems: "flex-start" }}>
                    <Bullet />
                    <span>
                        <ExternalCitation href="https://facebookexperimental.github.io/Robyn/">
                            Meta Robyn documentation
                        </ExternalCitation>
                        , An Analyst&apos;s Guide to MMM.
                    </span>
                </li>
                <li style={{ ...styles.li, display: "flex", alignItems: "flex-start" }}>
                    <Bullet />
                    <span>
                        <ExternalCitation href="https://research.google/pubs/pub46001/">
                            Google Research
                        </ExternalCitation>
                        , Bayesian Methods for Media Mix Modeling with Carryover and Shape
                        Effects.
                    </span>
                </li>
                <li style={{ ...styles.li, display: "flex", alignItems: "flex-start" }}>
                    <Bullet />
                    <span>
                        <ExternalCitation href="https://www.thinkwithgoogle.com/marketing-strategies/data-and-measurement/marketing-mix-model-guide/">
                            Think with Google
                        </ExternalCitation>
                        , Marketing Mix Modeling Guidebook.
                    </span>
                </li>
            </ul>
        </div>
    );
}
