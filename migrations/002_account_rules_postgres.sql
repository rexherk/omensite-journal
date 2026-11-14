-- Existing real accounts remain unconfirmed until their owner saves a plan.
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS rule_profile TEXT;
