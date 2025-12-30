"use client";


interface PricingFeature {
  text: string;
  included: boolean;
}

interface PricingCardProps {
  name: string;
  price: number;
  interval: "month" | "year";
  description: string;
  features: PricingFeature[];
  isPopular?: boolean;
  isCurrentPlan?: boolean;
  onSelect: () => void;
  buttonText?: string;
  loading?: boolean;
}

export default function PricingCard({
  name,
  price,
  interval,
  description,
  features,
  isPopular = false,
  isCurrentPlan = false,
  onSelect,
  buttonText = "Get Started",
  loading = false,
}: PricingCardProps) {
  return (
    <div
      className={`relative rounded-2xl p-6 transition-all ${
        isPopular
          ? "bg-gradient-to-b from-gold-400/10 to-obsidian-800 border-2 border-gold-400/50 shadow-gold"
          : "bg-obsidian-800 border border-obsidian-700 hover:border-obsidian-600"
      }`}
    >
      {/* Popular Badge */}
      {isPopular && (
        <div className="absolute -top-4 left-1/2 -translate-x-1/2">
          <span className="bg-gold-gradient text-obsidian-900 text-xs font-semibold px-4 py-1.5 rounded-full shadow-gold-sm">
            Most Popular
          </span>
        </div>
      )}

      {/* Current Plan Badge */}
      {isCurrentPlan && (
        <div className="absolute -top-4 left-1/2 -translate-x-1/2">
          <span className="bg-green-500 text-white text-xs font-semibold px-4 py-1.5 rounded-full">
            Current Plan
          </span>
        </div>
      )}

      {/* Header */}
      <div className="text-center mb-6 pt-2">
        <h3 className="font-display text-xl font-semibold text-cream-100 mb-2">{name}</h3>
        <p className="text-cream-500 text-sm">{description}</p>
      </div>

      {/* Price */}
      <div className="text-center mb-6">
        <div className="flex items-baseline justify-center gap-1">
          <span className="text-cream-500">$</span>
          <span className="font-display text-5xl font-bold text-cream-100">{price}</span>
          <span className="text-cream-500">/{interval}</span>
        </div>
      </div>

      {/* Features */}
      <ul className="space-y-3 mb-8">
        {features.map((feature, i) => (
          <li key={i} className="flex items-start gap-3">
            {feature.included ? (
              <svg className="w-5 h-5 text-gold-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            ) : (
              <svg className="w-5 h-5 text-cream-600 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            )}
            <span className={feature.included ? "text-cream-300" : "text-cream-600"}>
              {feature.text}
            </span>
          </li>
        ))}
      </ul>

      {/* CTA Button */}
      <button
        onClick={onSelect}
        disabled={isCurrentPlan || loading}
        className={`w-full py-3 px-6 rounded-xl font-medium transition-all ${
          isPopular
            ? "btn-gold"
            : isCurrentPlan
            ? "bg-obsidian-700 text-cream-500 cursor-not-allowed"
            : "btn-outline-gold"
        } ${loading ? "opacity-50 cursor-wait" : ""}`}
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
            Processing...
          </span>
        ) : isCurrentPlan ? (
          "Current Plan"
        ) : (
          buttonText
        )}
      </button>
    </div>
  );
}

interface PricingToggleProps {
  interval: "month" | "year";
  onChange: (interval: "month" | "year") => void;
}

export function PricingToggle({ interval, onChange }: PricingToggleProps) {
  return (
    <div className="flex items-center justify-center gap-4">
      <span className={`text-sm ${interval === "month" ? "text-cream-100" : "text-cream-500"}`}>
        Monthly
      </span>
      <button
        onClick={() => onChange(interval === "month" ? "year" : "month")}
        className="relative w-14 h-7 rounded-full bg-obsidian-700 border border-obsidian-600 transition-colors"
      >
        <span
          className={`absolute top-0.5 w-6 h-6 rounded-full bg-gold-400 transition-transform ${
            interval === "year" ? "left-7" : "left-0.5"
          }`}
        />
      </button>
      <span className={`text-sm ${interval === "year" ? "text-cream-100" : "text-cream-500"}`}>
        Yearly
        <span className="ml-2 text-xs text-gold-400">Save 20%</span>
      </span>
    </div>
  );
}

// Predefined pricing plans data
export const pricingPlans = {
  free: {
    name: "Starter",
    price: 0,
    description: "Perfect for trying out Discord Analytics",
    features: [
      { text: "500 MB storage", included: true },
      { text: "1,000 queries/month", included: true },
      { text: "3 extractions/month", included: true },
      { text: "7-day data retention", included: true },
      { text: "Basic analytics", included: true },
      { text: "Email support", included: false },
      { text: "API access", included: false },
      { text: "Webhooks", included: false },
    ],
  },
  pro: {
    name: "Professional",
    price: 9,
    yearlyPrice: 86,
    description: "For power users and small teams",
    features: [
      { text: "5 GB storage", included: true },
      { text: "Unlimited queries", included: true },
      { text: "Unlimited extractions", included: true },
      { text: "90-day data retention", included: true },
      { text: "Advanced analytics", included: true },
      { text: "Priority email support", included: true },
      { text: "API access", included: true },
      { text: "Webhooks", included: false },
    ],
  },
  team: {
    name: "Enterprise",
    price: 29,
    yearlyPrice: 278,
    description: "For large communities and businesses",
    features: [
      { text: "50 GB storage", included: true },
      { text: "Unlimited queries", included: true },
      { text: "Unlimited extractions", included: true },
      { text: "Unlimited data retention", included: true },
      { text: "Custom analytics", included: true },
      { text: "24/7 priority support", included: true },
      { text: "Full API access", included: true },
      { text: "Webhooks & integrations", included: true },
    ],
  },
};
