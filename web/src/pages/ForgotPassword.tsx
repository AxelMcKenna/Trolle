import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Mail } from "lucide-react";
import { supabase } from "@/lib/supabase";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const ForgotPassword = () => {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!supabase) return;

    setLoading(true);
    setError(null);

    const { error: resetError } = await supabase.auth.resetPasswordForEmail(
      email,
      { redirectTo: `${window.location.origin}/auth/callback` }
    );

    setLoading(false);

    if (resetError) {
      setError(resetError.message);
    } else {
      setSent(true);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-primary px-4 py-3">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <Link to="/" className="text-lg font-bold text-white font-sans tracking-[0.15em]">TROLL-E</Link>
          <Link to="/login">
            <Button variant="ghost" size="sm" className="text-white hover:bg-white/10 gap-1.5">
              <ArrowLeft className="h-4 w-4" />
              Back to Sign In
            </Button>
          </Link>
        </div>
      </header>

      <div className="flex items-center justify-center px-4 py-16">
        <div className="w-full max-w-sm">
          {sent ? (
            <div className="text-center">
              <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-primary/10 mb-4">
                <Mail className="h-7 w-7 text-primary" />
              </div>
              <h1 className="text-2xl font-bold text-primary font-sans tracking-[0.15em] mb-2">Check your email</h1>
              <p className="text-gray-600 mb-6">
                We sent a password reset link to <span className="font-medium">{email}</span>.
              </p>
              <Link to="/login">
                <Button variant="outline" className="w-full">Back to Sign In</Button>
              </Link>
            </div>
          ) : (
            <>
              <div className="text-center mb-8">
                <h1 className="text-2xl font-bold text-primary font-sans tracking-[0.15em]">Reset Password</h1>
                <p className="text-gray-600 mt-2">Enter your email to receive a reset link</p>
              </div>

              <div className="bg-white rounded-xl shadow-sm border p-6 space-y-4">
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div>
                    <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                      Email
                    </label>
                    <Input
                      id="email"
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="you@example.com"
                      required
                    />
                  </div>

                  {error && (
                    <p className="text-sm text-destructive">{error}</p>
                  )}

                  <Button type="submit" className="w-full" disabled={loading}>
                    {loading ? "Sending..." : "Send Reset Link"}
                  </Button>
                </form>
              </div>

              <p className="text-center text-sm text-gray-600 mt-4">
                Remember your password?{" "}
                <Link to="/login" className="text-primary font-medium hover:underline">
                  Sign in
                </Link>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default ForgotPassword;
