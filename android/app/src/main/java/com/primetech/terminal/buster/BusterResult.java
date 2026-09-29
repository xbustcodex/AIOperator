package com.primetech.terminal.buster;

import android.os.Parcel;
import android.os.Parcelable;

public final class BusterResult implements Parcelable {
    public final int statusCode;
    public final String operationId;
    public final String correlationId;
    public final String message;
    public final String output;
    public final int exitCode;
    public final boolean timedOut;
    public final boolean truncated;

    public BusterResult(
            int statusCode,
            String operationId,
            String correlationId,
            String message,
            String output,
            int exitCode,
            boolean timedOut,
            boolean truncated
    ) {
        this.statusCode = statusCode;
        this.operationId = operationId;
        this.correlationId = correlationId;
        this.message = message;
        this.output = output;
        this.exitCode = exitCode;
        this.timedOut = timedOut;
        this.truncated = truncated;
    }

    protected BusterResult(Parcel in) {
        statusCode = in.readInt();
        operationId = in.readString();
        correlationId = in.readString();
        message = in.readString();
        output = in.readString();
        exitCode = in.readInt();
        timedOut = in.readInt() != 0;
        truncated = in.readInt() != 0;
    }

    @Override
    public int describeContents() {
        return 0;
    }

    @Override
    public void writeToParcel(Parcel dest, int flags) {
        dest.writeInt(statusCode);
        dest.writeString(operationId);
        dest.writeString(correlationId);
        dest.writeString(message);
        dest.writeString(output);
        dest.writeInt(exitCode);
        dest.writeInt(timedOut ? 1 : 0);
        dest.writeInt(truncated ? 1 : 0);
    }

    public static final Creator<BusterResult> CREATOR = new Creator<BusterResult>() {
        @Override
        public BusterResult createFromParcel(Parcel in) {
            return new BusterResult(in);
        }

        @Override
        public BusterResult[] newArray(int size) {
            return new BusterResult[size];
        }
    };
}
