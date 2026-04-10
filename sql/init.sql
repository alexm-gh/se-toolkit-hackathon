-- TTMM Database Schema - Version 1

-- Profiles table with extensible fields via JSONB
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    level VARCHAR(50) NOT NULL CHECK (level IN ('beginner', 'intermediate', 'advanced', 'professional')),
    available_time JSONB NOT NULL DEFAULT '[]'::jsonb,
    desired_place JSONB NOT NULL DEFAULT '[]'::jsonb,
    preferences JSONB NOT NULL DEFAULT '[]'::jsonb,
    contact_info JSONB NOT NULL DEFAULT '{}'::jsonb,
    additional_info JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Match requests table for contact sharing approval
CREATE TABLE IF NOT EXISTS match_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sender_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    receiver_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    sender_approved BOOLEAN NOT NULL DEFAULT FALSE,
    receiver_approved BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'declined')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT different_users CHECK (sender_id != receiver_id),
    CONSTRAINT unique_request UNIQUE (sender_id, receiver_id)
);

-- Index for faster queries
CREATE INDEX idx_profiles_level ON profiles(level);
CREATE INDEX idx_profiles_place ON profiles(desired_place);
CREATE INDEX idx_match_requests_sender ON match_requests(sender_id);
CREATE INDEX idx_match_requests_receiver ON match_requests(receiver_id);

-- Trigger to update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_profiles_updated_at BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_match_requests_updated_at BEFORE UPDATE ON match_requests
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
