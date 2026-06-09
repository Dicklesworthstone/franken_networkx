// Validate: cyclic-Jacobi eigendecomp exp(A) vs scaling-squaring, dense vs sparse.
use std::time::Instant;

fn matmul_rowmajor(a: &[f64], b: &[f64], n: usize) -> Vec<f64> {
    let mut c = vec![0.0_f64; n * n];
    for i in 0..n {
        let a_row = &a[i * n..i * n + n];
        let c_row = &mut c[i * n..i * n + n];
        for k in 0..n {
            let aik = a_row[k];
            if aik == 0.0 { continue; }
            let b_row = &b[k * n..k * n + n];
            for j in 0..n { c_row[j] += aik * b_row[j]; }
        }
    }
    c
}

// shipped scaling-and-squaring
fn ss_exp(a: &[f64], n: usize) -> Vec<f64> {
    if n == 0 { return Vec::new(); }
    let mut norm = 0.0_f64;
    for i in 0..n {
        let mut row = 0.0_f64;
        for j in 0..n { row += a[i * n + j].abs(); }
        norm = norm.max(row);
    }
    let s: u32 = if norm > 0.5 { (norm / 0.5).log2().ceil() as u32 } else { 0 };
    let scale = 2.0_f64.powi(-(s as i32));
    let b: Vec<f64> = a.iter().map(|&x| x * scale).collect();
    let mut result = vec![0.0_f64; n * n];
    let mut term = vec![0.0_f64; n * n];
    for i in 0..n { result[i * n + i] = 1.0; term[i * n + i] = 1.0; }
    for k in 1..=30_u32 {
        let mut next = matmul_rowmajor(&term, &b, n);
        let inv_k = 1.0 / f64::from(k);
        let mut mx = 0.0_f64;
        for x in next.iter_mut() { *x *= inv_k; mx = mx.max(x.abs()); }
        for idx in 0..n * n { result[idx] += next[idx]; }
        term = next;
        if mx < 1e-15 { break; }
    }
    for _ in 0..s { result = matmul_rowmajor(&result, &result, n); }
    result
}

// cyclic Jacobi symmetric eigendecomp; returns (eigvals, eigvecs row-major V[i*n+j]=col j comp i)
fn jacobi_eig(a_in: &[f64], n: usize) -> (Vec<f64>, Vec<f64>) {
    let mut a = a_in.to_vec();
    let mut v = vec![0.0_f64; n * n];
    for i in 0..n { v[i * n + i] = 1.0; }
    if n == 0 { return (Vec::new(), v); }
    fn off_sq(a: &[f64], n: usize) -> f64 {
        let mut s = 0.0;
        for p in 0..n { for q in (p + 1)..n { s += a[p * n + q] * a[p * n + q]; } }
        s
    }
    let initial = off_sq(&a, n).max(1e-300);
    for _sweep in 0..100 {
        if off_sq(&a, n) <= 1e-30 * initial { break; }
        for p in 0..n {
            for q in (p + 1)..n {
                let apq = a[p * n + q];
                if apq.abs() < 1e-300 { continue; }
                let app = a[p * n + p];
                let aqq = a[q * n + q];
                let theta = (aqq - app) / (2.0 * apq);
                let t = theta.signum() / (theta.abs() + (theta * theta + 1.0).sqrt());
                let c = 1.0 / (t * t + 1.0).sqrt();
                let s = t * c;
                // rotate rows/cols p,q of A
                for k in 0..n {
                    let akp = a[k * n + p];
                    let akq = a[k * n + q];
                    a[k * n + p] = c * akp - s * akq;
                    a[k * n + q] = s * akp + c * akq;
                }
                for k in 0..n {
                    let apk = a[p * n + k];
                    let aqk = a[q * n + k];
                    a[p * n + k] = c * apk - s * aqk;
                    a[q * n + k] = s * apk + c * aqk;
                }
                // accumulate eigenvectors
                for k in 0..n {
                    let vkp = v[k * n + p];
                    let vkq = v[k * n + q];
                    v[k * n + p] = c * vkp - s * vkq;
                    v[k * n + q] = s * vkp + c * vkq;
                }
            }
        }
    }
    let eig: Vec<f64> = (0..n).map(|i| a[i * n + i]).collect();
    (eig, v)
}

fn jac_exp(a: &[f64], n: usize) -> Vec<f64> {
    if n == 0 { return Vec::new(); }
    let (eig, v) = jacobi_eig(a, n);
    // W = V * diag(exp(eig))  (scale column j by exp(eig[j]))
    let mut w = vec![0.0_f64; n * n];
    for i in 0..n {
        for j in 0..n { w[i * n + j] = v[i * n + j] * eig[j].exp(); }
    }
    // exp(A) = W * V^T ; build V^T
    let mut vt = vec![0.0_f64; n * n];
    for i in 0..n { for j in 0..n { vt[j * n + i] = v[i * n + j]; } }
    matmul_rowmajor(&w, &vt, n)
}

fn make_adj(n: usize, d: usize, seed: u64) -> Vec<f64> {
    let mut a = vec![0.0_f64; n * n];
    let mut st = seed.wrapping_mul(0x9E3779B97F4A7C15).wrapping_add(1);
    let mut nx = || { st ^= st << 13; st ^= st >> 7; st ^= st << 17; st };
    let te = n * d / 2;
    let mut e = 0;
    while e < te {
        let i = (nx() as usize) % n;
        let j = (nx() as usize) % n;
        if i != j && a[i * n + j] == 0.0 { a[i * n + j] = 1.0; a[j * n + i] = 1.0; e += 1; }
    }
    a
}
fn max_rel(x: &[f64], y: &[f64]) -> f64 {
    let mut m = 0.0_f64;
    for k in 0..x.len() {
        let den = if y[k].abs() > 1e-9 { y[k].abs() } else { 1.0 };
        m = m.max((x[k] - y[k]).abs() / den);
    }
    m
}
fn main() {
    for &(n, d) in &[(120usize, 6usize), (200, 6), (120, 60), (200, 100), (200, 199), (300, 290)] {
        let a = make_adj(n, d, 99);
        let density = d as f64 / n as f64;
        let e1 = ss_exp(&a, n);
        let e2 = jac_exp(&a, n);
        let rel = max_rel(&e2, &e1);
        let reps = if n <= 200 { 15 } else { 6 };
        let t0 = Instant::now();
        for _ in 0..reps { std::hint::black_box(ss_exp(&a, n)); }
        let t_ss = t0.elapsed().as_secs_f64() * 1000.0 / reps as f64;
        let t1 = Instant::now();
        for _ in 0..reps { std::hint::black_box(jac_exp(&a, n)); }
        let t_jac = t1.elapsed().as_secs_f64() * 1000.0 / reps as f64;
        println!("n={n:4} d={d:4} dens={density:4.2}  ss {t_ss:8.3}ms  jacobi {t_jac:8.3}ms  ss/jac {:5.2}x  rel={rel:.1e}", t_ss / t_jac);
    }
}
