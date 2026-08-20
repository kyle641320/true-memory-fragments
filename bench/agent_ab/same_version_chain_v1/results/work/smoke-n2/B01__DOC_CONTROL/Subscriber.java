/*
 * Copyright (C) 2014 The Guava Authors
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
 * in compliance with the License. You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software distributed under the License
 * is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
 * or implied. See the License for the specific language governing permissions and limitations under
 * the License.
 */

package com.google.common.eventbus;

import static com.google.common.base.Preconditions.checkNotNull;

import com.google.common.annotations.VisibleForTesting;
import com.google.j2objc.annotations.Weak;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.concurrent.Executor;
import org.jspecify.annotations.Nullable;

/**
 * A subscriber method on a specific object, plus the executor that should be used for dispatching
 * events to it.
 *
 * <p>Two subscribers are equivalent when they refer to the same method on the same object (not
 * class). This property is used to ensure that no subscriber method is registered more than once.
 *
 * @author Colin Decker
 */
class Subscriber {

  /** Creates a {@code Subscriber} for {@code method} on {@code listener}. */
  static Subscriber create(EventBus bus, Object listener, Method method) {
    return isDeclaredThreadSafe(method)
        ? new Subscriber(bus, listener, method)
        : new SynchronizedSubscriber(bus, listener, method);
  }

  /** The event bus this subscriber belongs to. */
  @Weak private final EventBus bus;

  /** The object with the subscriber method. */
  @VisibleForTesting final Object target;

  /** Subscriber method. */
  private final Method method;

  /** Executor to use for dispatching events to this subscriber. */
  private final Executor executor;

  private static final int MAX_EVENTS_PER_SECOND = 100;
  private static final long RATE_LIMIT_INTERVAL_NANOS = 1_000_000_000L;

  /* Guarded by this because executor tasks may run concurrently. */
  private final long[] invocationTimes = new long[MAX_EVENTS_PER_SECOND];
  private int invocationCount;
  private int oldestInvocation;

  private Subscriber(EventBus bus, Object target, Method method) {
    this.bus = bus;
    this.target = checkNotNull(target);
    this.method = method;
    method.setAccessible(true);

    this.executor = bus.executor();
  }

  /** Dispatches {@code event} to this subscriber using the proper executor. */
  final void dispatchEvent(Object event) {
    executor.execute(
        () -> {
          if (!tryAcquireInvocation()) {
            return;
          }
          try {
            invokeSubscriberMethod(event);
          } catch (InvocationTargetException e) {
            bus.handleSubscriberException(e.getCause(), context(event));
          }
        });
  }

  /** Returns whether this subscriber may begin another invocation now. */
  private synchronized boolean tryAcquireInvocation() {
    long now = System.nanoTime();
    if (invocationCount < MAX_EVENTS_PER_SECOND) {
      int insertionPoint = (oldestInvocation + invocationCount) % MAX_EVENTS_PER_SECOND;
      invocationTimes[insertionPoint] = now;
      invocationCount++;
      return true;
    }

    if (now - invocationTimes[oldestInvocation] < RATE_LIMIT_INTERVAL_NANOS) {
      return false;
    }

    invocationTimes[oldestInvocation] = now;
    oldestInvocation = (oldestInvocation + 1) % MAX_EVENTS_PER_SECOND;
    return true;
  }

  /**
   * Invokes the subscriber method. This method can be overridden to make the invocation
   * synchronized.
   */
  @VisibleForTesting
  void invokeSubscriberMethod(Object event) throws InvocationTargetException {
    try {
      method.invoke(target, checkNotNull(event));
    } catch (IllegalArgumentException e) {
      throw new Error("Method rejected target/argument: " + event, e);
    } catch (IllegalAccessException e) {
      throw new Error("Method became inaccessible: " + event, e);
    } catch (InvocationTargetException e) {
      if (e.getCause() instanceof Error) {
        throw (Error) e.getCause();
      }
      throw e;
    }
  }

  /** Gets the context for the given event. */
  private SubscriberExceptionContext context(Object event) {
    return new SubscriberExceptionContext(bus, event, target, method);
  }

  @Override
  public final int hashCode() {
    return (31 + method.hashCode()) * 31 + System.identityHashCode(target);
  }

  @SuppressWarnings("ReferenceEquality") // see comment below
  @Override
  public final boolean equals(@Nullable Object obj) {
    if (obj instanceof Subscriber) {
      Subscriber that = (Subscriber) obj;
      // Use == so that different equal instances will still receive events.
      // We only guard against the case that the same object is registered
      // multiple times
      return target == that.target && method.equals(that.method);
    }
    return false;
  }

  /**
   * Checks whether {@code method} is thread-safe, as indicated by the presence of the {@link
   * AllowConcurrentEvents} annotation.
   */
  private static boolean isDeclaredThreadSafe(Method method) {
    return method.getAnnotation(AllowConcurrentEvents.class) != null;
  }

  /**
   * Subscriber that synchronizes invocations of a method to ensure that only one thread may enter
   * the method at a time.
   */
  @VisibleForTesting
  static final class SynchronizedSubscriber extends Subscriber {

    private SynchronizedSubscriber(EventBus bus, Object target, Method method) {
      super(bus, target, method);
    }

    @Override
    void invokeSubscriberMethod(Object event) throws InvocationTargetException {
      synchronized (this) {
        super.invokeSubscriberMethod(event);
      }
    }
  }
}
