// Isolated before/after micro-benchmark + parity check for matrix_exp_symmetric.
// Both kernels copy-pasted; no crate dependency. Compile: rustc -O.
use std::time::Instant;

// ---- OLD: naive 60-term Taylor, full O(n^3) matmul per term (i-j-l order) ----
fn old_matrix_exp(a: &[f64], n: usize) -> Vec<f64> {
    let mut result = vec![0.0_f64; n * n];
    let mut term = vec![0.0_f64; n * n];
    for i in 0..n {
        term[i * n + i] = 1.0;
        result[i * n + i] = 1.0;
    }
    for k in 1..=60 {
        let prev = term.clone();
        for i in 0..n {
            for j in 0..n {
                let mut s = 0.0;
                for l in 0..n {
                    s += prev[i * n + l] * a[l * n + j];
                }
                term[i * n + j] = s / k as f64;
            }
        }
        let mut max_term = 0.0_f64;
        for i in 0..n {
            for j in 0..n {
                result[i * n + j] += term[i * n + j];
                max_term = max_term.max(term[i * n + j].abs());
            }
        }
        if max_term < 1e-15 {
            break;
        }
    }
    result
}

// ---- NEW: scaling-and-squaring + cache-friendly i-k-j matmul ----
fn matmul_rowmajor(a: &[f64], b: &[f64], n: usize) -> Vec<f64> {
    let mut c = vec![0.0_f64; n * n];
    for i in 0..n {
        let a_row = &a[i * n..i * n + n];
        let c_row = &mut c[i * n..i * n + n];
        for k in 0..n {
            let aik = a_row[k];
            if aik == 0.0 {
                continue;
            }
            let b_row = &b[k * n..k * n + n];
            for j in 0..n {
                c_row[j] += aik * b_row[j];
            }
        }
    }
    c
}
fn new_matrix_exp(a: &[f64], n: usize) -> Vec<f64> {
    if n == 0 {
        return Vec::new();
    }
    let mut norm = 0.0_f64;
    for i in 0..n {
        let mut row = 0.0_f64;
        for j in 0..n {
            row += a[i * n + j].abs();
        }
        norm = norm.max(row);
    }
    let s: u32 = if norm > 0.5 {
        (norm / 0.5).log2().ceil() as u32
    } else {
        0
    };
    let scale = 2.0_f64.powi(-(s as i32));
    let b: Vec<f64> = a.iter().map(|&x| x * scale).collect();
    let mut result = vec![0.0_f64; n * n];
    let mut term = vec![0.0_f64; n * n];
    for i in 0..n {
        result[i * n + i] = 1.0;
        term[i * n + i] = 1.0;
    }
    for k in 1..=30_u32 {
        let mut next = matmul_rowmajor(&term, &b, n);
        let inv_k = 1.0 / f64::from(k);
        let mut max_term = 0.0_f64;
        for x in next.iter_mut() {
            *x *= inv_k;
            max_term = max_term.max(x.abs());
        }
        for idx in 0..n * n {
            result[idx] += next[idx];
        }
        term = next;
        if max_term < 1e-15 {
            break;
        }
    }
    for _ in 0..s {
        result = matmul_rowmajor(&result, &result, n);
    }
    result
}

// deterministic pseudo-random symmetric adjacency (avg degree d) + accuracy ref
fn make_adj(n: usize, d: usize, seed: u64) -> Vec<f64> {
    let mut a = vec![0.0_f64; n * n];
    let mut state = seed.wrapping_mul(0x9E3779B97F4A7C15).wrapping_add(1);
    let mut next = || {
        state ^= state << 13;
        state ^= state >> 7;
        state ^= state << 17;
        state
    };
    let target_edges = n * d / 2;
    let mut e = 0;
    while e < target_edges {
        let i = (next() as usize) % n;
        let j = (next() as usize) % n;
        if i != j && a[i * n + j] == 0.0 {
            a[i * n + j] = 1.0;
            a[j * n + i] = 1.0;
            e += 1;
        }
    }
    a
}

fn max_rel(x: &[f64], y: &[f64]) -> f64 {
    let mut m = 0.0_f64;
    for k in 0..x.len() {
        let denom = if y[k].abs() > 1e-12 { y[k].abs() } else { 1.0 };
        m = m.max((x[k] - y[k]).abs() / denom);
    }
    m
}

fn main() {
    for &(n, d) in &[(120usize, 6usize), (220, 6), (220, 20), (300, 40)] {
        let a = make_adj(n, d, 12345);
        // warm + correctness
        let o = old_matrix_exp(&a, n);
        let m = new_matrix_exp(&a, n);
        let rel = max_rel(&m, &o);
        // time old
        let reps = if n <= 220 { 20 } else { 8 };
        let t0 = Instant::now();
        for _ in 0..reps {
            std::hint::black_box(old_matrix_exp(&a, n));
        }
        let t_old = t0.elapsed().as_secs_f64() * 1000.0 / reps as f64;
        let t1 = Instant::now();
        for _ in 0..reps {
            std::hint::black_box(new_matrix_exp(&a, n));
        }
        let t_new = t1.elapsed().as_secs_f64() * 1000.0 / reps as f64;
        println!(
            "n={n:4} d={d:3}  old {t_old:8.3}ms  new {t_new:8.3}ms  speedup {:6.2}x  max_rel(new,old)={rel:.2e}",
            t_old / t_new
        );
    }
}
