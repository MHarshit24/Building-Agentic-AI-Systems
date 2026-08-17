import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { login } from "../api/endpoints";
import { useAuthStore } from "../store/authStore";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Spinner } from "../components/ui/Spinner";
import { AuthLayout } from "../components/layout/AuthLayout";

const schema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});
type FormValues = z.infer<typeof schema>;

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const setSession = useAuthStore((s) => s.setSession);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    setServerError(null);
    try {
      const res = await login(values);
      setSession(res.access_token, res.refresh_token, res.role);
      const from = (location.state as { from?: { pathname: string } } | null)?.from?.pathname ?? "/";
      navigate(from, { replace: true });
    } catch {
      setServerError("Invalid email or password.");
    }
  };

  return (
    <AuthLayout
      title="Support Intelligence"
      subtitle="Sign in to continue"
      footer={
        <div className="flex items-center justify-between">
          <Link to="/forgot-password" className="font-medium text-brand-600 hover:underline dark:text-brand-400">
            Forgot password?
          </Link>
          <Link to="/signup" className="font-medium text-brand-600 hover:underline dark:text-brand-400">
            Create account
          </Link>
        </div>
      }
    >
      <form className="space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
        <Input
          label="Email"
          type="email"
          autoComplete="username"
          error={errors.email?.message}
          {...register("email")}
        />
        <Input
          label="Password"
          type="password"
          autoComplete="current-password"
          error={errors.password?.message}
          {...register("password")}
        />
        {serverError && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
            {serverError}
          </p>
        )}
        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? <Spinner /> : "Sign in"}
        </Button>
      </form>
    </AuthLayout>
  );
}
