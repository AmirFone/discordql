import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center">
      <SignIn
        appearance={{
          elements: {
            formButtonPrimary: "bg-indigo-600 hover:bg-indigo-700",
            card: "bg-gray-800 border-gray-700",
            headerTitle: "text-white",
            headerSubtitle: "text-gray-400",
            socialButtonsBlockButton: "bg-gray-700 border-gray-600 text-white hover:bg-gray-600",
            formFieldLabel: "text-gray-300",
            formFieldInput: "bg-gray-700 border-gray-600 text-white",
            footerActionLink: "text-indigo-400 hover:text-indigo-300",
          },
        }}
      />
    </div>
  );
}
