set N;                  # все узлы
set A within {N, N};    # допустимые дуги

param c{A} >= 0;        # стоимость (км)

param start symbolic;
param finish symbolic;

set STOPS := N diff {start, finish};

var x{(i,j) in A}, binary;
var u{i in N} >= 0, <= card(N);

minimize TotalCost:
    sum{(i,j) in A} c[i,j] * x[i,j];

# Из start выходит ровно одна дуга
s.t. StartOut:
    sum{(start,j) in A} x[start,j] = 1;

# В start ничего не входит
s.t. StartIn:
    sum{(i,start) in A} x[i,start] = 0;

# В finish входит ровно одна дуга
s.t. FinishIn:
    sum{(i,finish) in A} x[i,finish] = 1;

# Из finish ничего не выходит
s.t. FinishOut:
    sum{(finish,j) in A} x[finish,j] = 0;

# Для каждого stop: ровно одна входящая дуга
s.t. StopIn{k in STOPS}:
    sum{(i,k) in A} x[i,k] = 1;

# Для каждого stop: ровно одна исходящая дуга
s.t. StopOut{k in STOPS}:
    sum{(k,j) in A} x[k,j] = 1;

# MTZ: фиксируем порядок start
s.t. StartOrder:
    u[start] = 0;

# MTZ-подобные ограничения от подциклов
s.t. SubtourElimination{(i,j) in A: i != start and j != start and i != j}:
    u[i] - u[j] + card(N) * x[i,j] <= card(N) - 1;

solve;

printf "Objective_km=%.6f\n", TotalCost;
printf "SelectedArcsBegin\n";
for {(i,j) in A: x[i,j] > 0.5} {
    printf "%s,%s,%.6f\n", i, j, c[i,j];
}
printf "SelectedArcsEnd\n";

end;