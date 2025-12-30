import { SignIn } from "@clerk/nextjs";
import Link from "next/link";

export default function SignInPage() {
  return (
    <div className="min-h-screen bg-obsidian-900 flex flex-col">
      {/* Navigation */}
      <nav className="container mx-auto px-6 py-6">
        <Link href="/" className="flex items-center gap-3 w-fit">
          <div className="w-9 h-9 rounded-lg bg-gold-gradient flex items-center justify-center shadow-gold-sm">
            <svg className="w-5 h-5 text-obsidian-900" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </div>
          <span className="font-display text-lg font-semibold text-gold-gradient">
            Discord Analytics
          </span>
        </Link>
      </nav>

      {/* Sign In Form */}
      <div className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <div className="text-center mb-8">
            <h1 className="font-display text-3xl font-bold text-cream-100 mb-2">
              Welcome back
            </h1>
            <p className="text-cream-500">
              Sign in to access your Discord Analytics dashboard
            </p>
          </div>

          <SignIn
            appearance={{
              elements: {
                rootBox: "mx-auto",
                card: "bg-obsidian-800 border border-obsidian-700 shadow-gold-sm",
                headerTitle: "text-cream-100 font-display",
                headerSubtitle: "text-cream-400",
                socialButtonsBlockButton: "bg-obsidian-700 border border-obsidian-600 text-cream-100 hover:bg-obsidian-600 hover:border-gold-400/30",
                socialButtonsBlockButtonText: "text-cream-100 font-medium",
                dividerLine: "bg-obsidian-600",
                dividerText: "text-cream-500",
                formFieldLabel: "text-cream-300 font-medium",
                formFieldInput: "bg-obsidian-700 border-obsidian-600 text-cream-100 focus:border-gold-400 focus:ring-gold-400/20",
                formButtonPrimary: "bg-gold-gradient hover:opacity-90 text-obsidian-900 font-semibold",
                footerActionLink: "text-gold-400 hover:text-gold-300 font-medium",
                footerActionText: "text-cream-500",
                identityPreviewText: "text-cream-100",
                identityPreviewEditButton: "text-gold-400 hover:text-gold-300",
                formFieldAction: "text-gold-400 hover:text-gold-300",
                alertText: "text-cream-300",
                formFieldInputShowPasswordButton: "text-cream-400 hover:text-cream-200",
              },
              layout: {
                socialButtonsPlacement: "top",
                showOptionalFields: false,
              },
            }}
          />
        </div>
      </div>

      {/* Footer */}
      <footer className="container mx-auto px-6 py-6 text-center">
        <p className="text-cream-600 text-sm">
          &copy; 2025 Discord Analytics. All rights reserved.
        </p>
      </footer>
    </div>
  );
}
